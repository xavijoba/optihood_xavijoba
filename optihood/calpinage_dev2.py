# -*- coding: utf-8 -*-
"""
Created on Wed Jun 14 11:47:07 2023

@author: stefano.pauletta
"""
# from shapely import ops, geometry
from shapely.geometry import Point ,LineString
from shapely.geometry import box

import matplotlib.pyplot as plt
from shapely import affinity
import numpy as np
import pandas as pd
import math
import pvlib

class Calpinage_light:
    """class to compute the number of panels that can be fit
    to a rectangular surface L by W with orientation defined
    by the direction of the short sides. 0° is Nord, 90° is East,
    180° is South, 270° is West and 360° is nord. Orentations < 90° and > 270°
    are solved by mirroring the building orientation at 180° , so that orientations are from East to West only.
    """
    def __init__(self,orientation=180,lat=42.6,long=6,tilt=20, 
                 W=10,L=10,w=1,l=2.05,d_W=0.5,d_L=0.5,
                 tilt_EW=20,f_EW=False,f_plot=False,d_rows=0.6,
                 parallel="long",optimal=False,demand=None,irradiance=None):
        """ Orientation is the building orientation in degrees
            lat is the roof middle latitude
            W is the roof width in [m]
            L is the roof length in [m]
            w is the panel witdh in [m]
            l is the panel length in [m]
            d_W is the roof safety distance from the edge of the long side in [m]
            d_L is the roof safety distance from the edge of the short side in [m]
            tilt is the panel inclination wrt to the horizontal in degrees
            parallel can be "long", "short" or "South" for collectors alignment along
            the long or short side of the building or towards South
        """
        self.orientation=orientation
        self.azimut=180
        self.optimal=optimal
        self.W=W
        self.L=L
        self.lat=lat
        self.long=long
        self.w=w
        self.l=l
        self.d_W=d_W
        self.d_L=d_L
        # self.tilt=tilt
        self.tilt_EW=tilt_EW
        self.d_rows_min=d_rows
        self.off_pnl=0.07
        self.W_S_D=-23.45
        self.W_S_A=np.abs(self.lat+self.W_S_D)
        
        self.f_EW=f_EW
        self.f_plot=f_plot
        self.demand=demand
        self.ghi=irradiance[0]
        self.dhi=irradiance[1]
        self.dni=irradiance[2]
        self.fit_panel(tilt,parallel)
        self.tz='Europe/Zurich'
        self.site = pvlib.location.Location(self.lat, self.long, tz=self.tz)
        self.satisfy_demand()
        return None

    def satisfy_demand(self):
        solar_position = self.site.get_solarposition(times=self.ghi.index)
        POA_irradiance = pvlib.irradiance.get_total_irradiance(
                                surface_tilt=self.roof.loc[0,'tilt'],
                                surface_azimuth=self.conv_orient,                               
                                ghi=self.ghi,
                                dhi=self.dhi,
                                dni=self.dni,
                                solar_zenith=solar_position['apparent_zenith'],
                                solar_azimuth=solar_position['azimuth'])
        self.poa_irradiance=POA_irradiance['poa_global']
        self.production=self.poa_irradiance*self.roof.iloc[-1,1]
        return None
    
    def fit_panel(self,tilt,parallel):
        """
        Method to fit the reference collector to the availabe roof 
        based on orientation and tilt options.
        
        """        
        self.roof=pd.DataFrame(columns=['N_panel','ratio','tilt','cll_azimut','row_dist'])
        if self.orientation < 90 or self.orientation > 270:
                self.orientation = self.orientation + 180
                if self.orientation > 360 :
                    self.orientation=self.orientation-360
        
        
        
        #orient diff convention is 0°South, 90°West, -90°Est
        self.conv_orient=self.orientation-self.azimut
        
        if parallel=="short":
            if self.conv_orient>0:
                self.teta=-90
            else:
                self.teta=90
        elif parallel=='long':
            self.teta=0
        else:
            self.teta=-self.conv_orient
            
        
        B = box(0.0, 0.0, self.L, self.W)
        B1 = box(self.d_L, self.d_W, self.L-self.d_L, self.W-self.d_W)
  
        self.rows=pd.DataFrame(columns=['edge_south','edge_north','row_surf','N_panel'])
        print(self.teta)
        if self.f_EW!=True and self.optimal==True:
            PVGIS_data = pvlib.iotools.get_pvgis_hourly(self.lat, self.long,components=False,
                                                    surface_azimuth=self.teta+self.conv_orient,
                                                    start=2016,
                                                    end=2016,
                                                    optimal_surface_tilt=True,
                                                    optimalangles=False,
                                                    map_variables=True)
            self.tilt=PVGIS_data[1]['mounting_system']['fixed']['slope']['value']
        else:
            self.tilt=tilt
        
        if self.f_EW==True:
            self.w_loop=2*self.w*math.cos(math.radians(self.tilt_EW))+self.off_pnl
            # self.off_row=np.max([self.w*np.sin(np.radians(self.tilt_EW))*1/np.tan(np.radians(self.W_S_A)),self.d_rows_min])
            self.off_row=np.min([self.w*np.sin(np.radians(self.tilt_EW))*1/np.tan(np.radians(self.W_S_A)),self.d_rows_min])
            if self.teta % 90 ==0:
                if self.teta == -90: 
                    b3 = box(B1.bounds[2]-self.l, B1.bounds[3]-self.w_loop, 
                             B1.bounds[2], B1.bounds[3])
                    L_west=LineString([(B1.bounds[0], B1.bounds[3]), (B1.bounds[2], B1.bounds[3])]) 
                    L_east=L_west.parallel_offset(self.w_loop)
                    b6= box(L_west.bounds[0], L_west.bounds[1], 
                            L_east.bounds[2], L_east.bounds[3])
                    
                elif self.teta== 90:
                    b3 = box(B1.bounds[0], B1.bounds[3]-self.w_loop, 
                             B1.bounds[0]+self.l, B1.bounds[3])
                    L_west=LineString([(B1.bounds[0], B1.bounds[3]), (B1.bounds[2], B1.bounds[3])]) 
                    L_east=L_west.parallel_offset(self.w_loop)
                    b6= box(L_east.bounds[0], L_east.bounds[1], 
                            L_west.bounds[2], L_west.bounds[3])
                   
                elif self.teta== 0:
                    b3 = box(B1.bounds[0], B1.bounds[3]-self.l, 
                             B1.bounds[0]+self.w_loop, B1.bounds[3])
                    L_west=LineString([(B1.bounds[0], B1.bounds[1]), (B1.bounds[0], B1.bounds[3])]) 
                    L_east=L_west.parallel_offset(self.w_loop)
                    b6= box(L_east.bounds[0], L_east.bounds[1], 
                            L_west.bounds[2], L_west.bounds[3])
                    
                con_area=b3.area*self.off_pnl/self.l
                self.rows.loc[self.rows.index.size,'edge_south']=L_east.length
                self.rows.loc[self.rows.index.size-1,'edge_north']=L_west.length
                self.rows.loc[self.rows.index.size-1,'row_surf']=b6.area
                self.rows.loc[self.rows.index.size-1,'N_panel']=np.floor((b6.area+con_area)/(b3.area+con_area)) 
                if self.f_plot==True:
                    fig, ax = plt.subplots(figsize=(self.L, self.W))
                    ax.plot(*B.exterior.xy)
                    ax.plot(*B1.exterior.xy)
                    
                if self.rows.loc[self.rows.index.size-1,'N_panel']>0:
                    if self.teta==-90:
                        # b7=affinity.translate(b3,xoff=b6.bounds[0]-b3.bounds[0],
                        #                       yoff=b6.bounds[3]-b3.bounds[3])
                        b7=b3
                    elif self.teta==90:
                        b7=affinity.translate(b3,xoff=b6.bounds[0]-b3.bounds[0],
                                              yoff=b6.bounds[1]-b3.bounds[1])
                    elif self.teta == 0:
                        b7=affinity.translate(b3,xoff=b6.bounds[2]-b3.bounds[2],
                                              yoff=b6.bounds[2]-b3.bounds[2])
                            
                    
                    b7_xy=pd.DataFrame(b7.boundary.xy).sort_values(by=0,axis=1).T.drop_duplicates().T
                    # ax.plot(*b6.exterior.xy)
                    if self.f_plot==True:
                        ax.plot(*b7.exterior.xy)
                        
                    for z in range(0,int(self.rows.loc[self.rows.index.size-1,'N_panel'])):
                        
                        b8=affinity.translate(b7,xoff=z*(self.l+self.off_pnl)*np.sin(np.radians(self.teta)),
                                          yoff=-z*(self.l+self.off_pnl)*np.cos(np.radians(self.teta)))
                        
                        if self.f_plot==True:
                            ax.plot(*b8.exterior.xy)
                
                i=0
                L_west=L_west.parallel_offset(self.off_row+self.w_loop)#,side="rigth")
                L_east=L_east.parallel_offset(self.off_row+self.w_loop)#,side="rigth")
                while (L_west.intersection(B1).length and L_east.intersection(B1).length)>0:
                    i+=1
                
                    b6=box(L_west.intersection(B1).bounds[0], L_west.intersection(B1).bounds[1],
                           L_east.intersection(B1).bounds[2], L_east.intersection(B1).bounds[3])
                    b3_xy=pd.DataFrame(b3.boundary.xy).sort_values(by=0,axis=1).T.drop_duplicates().T
                    b6_xy=pd.DataFrame(b6.boundary.xy).sort_values(by=0,axis=1).T.drop_duplicates().T
                    # ax.plot(*b6.exterior.xy)
                    
                    self.rows.loc[self.rows.index.size,'edge_south']=L_east.intersection(B1).length
                    self.rows.loc[self.rows.index.size-1,'edge_north']=L_west.intersection(B1).length
                    self.rows.loc[self.rows.index.size-1,'N_panel']=np.floor((b6.area+con_area)/(b3.area+con_area)) 
                    self.rows.loc[self.rows.index.size-1,'row_surf']=b6.area   
                    if self.rows.loc[self.rows.index.size-1,'N_panel']>0:
                        if self.teta==-90:
                            b7=affinity.translate(b3,xoff=b6.bounds[2]-b3.bounds[2],
                                                  yoff=b6.bounds[3]-b3.bounds[3])
                        elif self.teta==90:
                            b7=affinity.translate(b3,xoff=b6.bounds[0]-b3.bounds[0],
                                                  yoff=b6.bounds[1]-b3.bounds[1])
                        elif self.teta == 0:
                            b7=affinity.translate(b3,xoff=b6.bounds[0]-b3.bounds[0],
                                                  yoff=b6.bounds[3]-b3.bounds[3])
                       
                        
                        b7_xy=pd.DataFrame(b7.boundary.xy).sort_values(by=0,axis=1).T.drop_duplicates().T
                        if self.f_plot==True:
                            ax.plot(*b7.exterior.xy)
                            
                        for z in range(1,int(self.rows.loc[self.rows.index.size-1,'N_panel'])):
                            b8=affinity.translate(b7,xoff=z*(self.l+self.off_pnl)*np.sin(np.radians(self.teta)),
                                                  yoff=(-z*(self.l+self.off_pnl)*np.cos(np.radians(self.teta))))
                            if self.f_plot==True:
                                ax.plot(*b8.exterior.xy)
                    L_west=L_west.parallel_offset(self.off_row+self.w_loop)#,side="rigth")
                    L_east=L_east.parallel_offset(self.off_row+self.w_loop)#,side="rigth")
                if self.f_plot==True:
                    plt.show()
                self.roof.loc[self.roof.index.size,'N_panel']=self.rows.loc[self.rows.index[-i]:,'N_panel'].sum()*2
                self.roof.loc[self.roof.index.size-1,'ratio']=self.roof.loc[self.roof.index.size-1,'N_panel']*self.l*self.w/B1.area
                self.roof.loc[self.roof.index.size-1,'tilt']=self.tilt
                self.roof.loc[self.roof.index.size-1,'cll_azimut']=self.teta+self.conv_orient
                self.roof.loc[self.roof.index.size-1,'row_dist']=self.off_row
                
            elif self.teta<0:
                b1 = box(B1.bounds[2]-self.l, B1.bounds[1], 
                         B1.bounds[2], B1.bounds[1]+self.w_loop)
                
                b2 = affinity.rotate(b1, -90+self.teta, (b1.bounds[0], b1.bounds[1]))
                b3=affinity.translate(b2,xoff=B1.bounds[2]-b2.bounds[2],
                                      yoff=B1.bounds[1]-b2.bounds[1])
                con_area=b3.area*self.off_pnl/self.l
                b3_xy=pd.DataFrame(b3.boundary.xy).sort_values(by=0,axis=1)
                
                L1=LineString([(B1.bounds[0], B1.bounds[1]), (B1.bounds[2], B1.bounds[1])]) 
                L1=affinity.rotate(L1,90+self.teta,(B1.bounds[2],B1.bounds[1]))
                L1=affinity.translate(L1,yoff=b3.bounds[1]+self.l*math.cos(math.radians(self.teta))
                                        -B1.bounds[1],xoff=0)
                L1=affinity.scale(L1,xfact=np.max([self.L/self.l,self.W/self.w_loop]),
                                    yfact=np.max([self.L/self.l,self.W/self.w_loop]))

                L_west=L1.parallel_offset(0)
                L_east=L_west.parallel_offset(-self.w_loop)
                self.rows.loc[self.rows.index.size,'edge_south']=L_east.intersection(B1).length
                self.rows.loc[self.rows.index.size-1,'edge_north']=L_west.intersection(B1).length
                self.rows.loc[self.rows.index.size-1,'N_panel']=1
                self.rows.loc[self.rows.index.size-1,'row_surf']=b3.area   
                
                if self.f_plot==True:
                    fig, ax = plt.subplots(figsize=(self.L, self.W))
                    ax.plot(*B.exterior.xy)
                    ax.plot(*B1.exterior.xy)
                    ax.plot(*b3.exterior.xy)
                    plt.xlim([-self.l, self.L+self.l])
                    plt.ylim([-self.w_loop, self.W+self.w_loop])
                # ax.plot(*b6.exterior.xy)
                # ax.plot(*L_east.xy)
                # ax.plot(*L_west.xy)
                
                
                i=0
                L_west=L_west.parallel_offset(self.off_row+self.w_loop,side="rigth")
                L_east=L_east.parallel_offset(self.off_row+self.w_loop,side="rigth")
                
                while (L_west.intersection(B1).length and L_east.intersection(B1).length)>0 :
                    i+=1
                    # ax.plot(*L_west.xy)
                    # ax.plot(*L_east.xy)
                    b4a = box(L_west.intersection(B1).bounds[0], L_west.intersection(B1).bounds[1], 
                             L_west.intersection(B1).bounds[0]-self.w_loop, L_west.intersection(B1).bounds[1]+L_west.intersection(B1).length)
                    b4 = affinity.rotate(b4a,self.teta, (L_west.intersection(B1).bounds[0],
                                                        L_west.intersection(B1).bounds[1]),
                                                                            use_radians=False)
                    
                    b5b = box(L_east.intersection(B1).bounds[2], L_east.intersection(B1).bounds[3], 
                             L_east.intersection(B1).bounds[2]+self.w_loop, L_east.intersection(B1).bounds[3]-L_east.intersection(B1).length)
                    b5 = affinity.rotate(b5b, self.teta, (L_east.intersection(B1).bounds[2],
                                                        L_east.intersection(B1).bounds[3]),
                                                                            use_radians=False)
                    # ax.plot(*b4.exterior.xy)
                    # ax.plot(*b5.exterior.xy)
                    b6=b4.intersection(b5)
                    # plt.show()
                    # try:
                    #     ax.plot(*b6.exterior.xy)
                    # except:
                    #     plt.show()                            
                    b3_xy=pd.DataFrame(b3.boundary.xy).sort_values(by=0,axis=1).T.drop_duplicates().T
                    b6_xy=pd.DataFrame(b6.boundary.xy).sort_values(by=0,axis=1).T.drop_duplicates().T
                    
                    self.rows.loc[self.rows.index.size,'edge_south']=L_east.intersection(B1).length
                    self.rows.loc[self.rows.index.size-1,'edge_north']=L_west.intersection(B1).length
                    self.rows.loc[self.rows.index.size-1,'N_panel']=np.floor((b6.area+con_area)/(b3.area+con_area)) 
                    self.rows.loc[self.rows.index.size-1,'row_surf']=b6.area   
                    if self.rows.loc[self.rows.index.size-1,'N_panel']>0:
                        
                        b7=affinity.translate(b3,xoff=b6.bounds[2]-b3.bounds[2],
                                              yoff=b6.bounds[3]-b3.bounds[3])
                        b7_xy=pd.DataFrame(b7.boundary.xy).sort_values(by=0,axis=1).T.drop_duplicates().T
                        if self.f_plot==True:
                            ax.plot(*b7.exterior.xy)
                            
                        for z in range(1,int(self.rows.loc[self.rows.index.size-1,'N_panel'])):
                            b8=affinity.translate(b7,xoff=z*((self.l+self.off_pnl)*np.sin(np.radians(self.teta))),
                                              yoff=-z*((self.l+self.off_pnl)*np.cos(np.radians(self.teta))))
                            if self.f_plot==True:
                                ax.plot(*b8.exterior.xy)
                    # ax.plot(*b5.exterior.xy)
                    L_west=L_west.parallel_offset(self.off_row+self.w_loop,side="rigth")
                    L_east=L_east.parallel_offset(self.off_row+self.w_loop,side="rigth")
                  
                if self.f_plot==True:
                    plt.show()
                self.roof.loc[self.roof.index.size,'N_panel']=self.rows.loc[self.rows.index[-i-1]:,'N_panel'].sum()*2
                self.roof.loc[self.roof.index.size-1,'ratio']=self.roof.loc[self.roof.index.size-1,'N_panel']*self.l*self.w/B1.area
                self.roof.loc[self.roof.index.size-1,'tilt']=self.tilt
                self.roof.loc[self.roof.index.size-1,'cll_azimut']=self.teta+self.conv_orient
                self.roof.loc[self.roof.index.size-1,'row_dist']=self.off_row
            elif self.teta>0:
                b1 = box(B1.bounds[0], B1.bounds[1], 
                         B1.bounds[0]+self.l, B1.bounds[1]+self.w_loop)
                
                b2 = affinity.rotate(b1, -90+self.teta, (b1.bounds[0], b1.bounds[1]))
                b3=affinity.translate(b2,xoff=0,
                                      yoff=B1.bounds[1]-b2.bounds[1])
                con_area=b3.area*self.off_pnl/self.l
                b3_xy=pd.DataFrame(b3.boundary.xy).sort_values(by=0,axis=1).T.drop_duplicates().T
                
                L1=LineString([(B1.bounds[0], B1.bounds[1]), (B1.bounds[2], B1.bounds[1])]) 
                L1=affinity.rotate(L1,-90+self.teta,(B1.bounds[0],B1.bounds[1]))
                L1=affinity.translate(L1,yoff=b3_xy.loc[1,b3_xy.loc[0,:]==b3_xy.loc[0,:].min()]
                                        -B1.bounds[1],xoff=0)
                L1=affinity.scale(L1,xfact=np.max([self.L/self.l,self.W/self.w_loop]),
                                    yfact=np.max([self.L/self.l,self.W/self.w_loop]))
                                                                                                                    
                L_west=L1.parallel_offset(0)
                L_east=L_west.parallel_offset(-self.w_loop)
                self.rows.loc[self.rows.index.size,'edge_south']=L_east.intersection(B1).length
                self.rows.loc[self.rows.index.size-1,'edge_north']=L_west.intersection(B1).length
                self.rows.loc[self.rows.index.size-1,'N_panel']=1
                self.rows.loc[self.rows.index.size-1,'row_surf']=b3.area   
                
                if self.f_plot==True:
                    fig, ax = plt.subplots(figsize=(self.L, self.W))
                    ax.plot(*B.exterior.xy)
                    ax.plot(*B1.exterior.xy)
                    ax.plot(*b3.exterior.xy)
                    plt.xlim([-self.l, self.L+self.l])
                    plt.ylim([-self.w_loop, self.W+self.w_loop])
                    # plt.show()
                i=0
                L_west=L_west.parallel_offset(self.off_row+self.w_loop,side="rigth")
                L_east=L_east.parallel_offset(self.off_row+self.w_loop,side="rigth")
                
                while (L_west.intersection(B1).length and L_east.intersection(B1).length)>0 :
                    i+=1
                    # ax.plot(*L_west.xy)
                    # ax.plot(*L_east.xy)
                    b4a = box(L_west.intersection(B1).bounds[2], L_west.intersection(B1).bounds[1], 
                             L_west.intersection(B1).bounds[2]+self.w_loop, L_west.intersection(B1).bounds[1]+L_west.intersection(B1).length)
                    b4 = affinity.rotate(b4a,self.teta, (L_west.intersection(B1).bounds[2],
                                                        L_west.intersection(B1).bounds[1]),
                                                                            use_radians=False)
                    
                    b5b = box(L_east.intersection(B1).bounds[2], L_east.intersection(B1).bounds[1], 
                             L_east.intersection(B1).bounds[2]-self.w_loop, L_east.intersection(B1).bounds[1]+L_east.intersection(B1).length)
                    b5 = affinity.rotate(b5b, self.teta, (L_east.intersection(B1).bounds[2],
                                                        L_east.intersection(B1).bounds[1]),
                                                                            use_radians=False)
                    # ax.plot(*b4.exterior.xy)
                    # ax.plot(*b5.exterior.xy)
                    b6=b4.intersection(b5)
                    # plt.show()
                    # try:
                    #     ax.plot(*b6.exterior.xy)
                    # except:
                    #     plt.show()                            
                    b3_xy=pd.DataFrame(b3.boundary.xy).sort_values(by=0,axis=1).T.drop_duplicates().T
                    b6_xy=pd.DataFrame(b6.boundary.xy).sort_values(by=0,axis=1).T.drop_duplicates().T
                    
                    self.rows.loc[self.rows.index.size,'edge_south']=L_east.intersection(B1).length
                    self.rows.loc[self.rows.index.size-1,'edge_north']=L_west.intersection(B1).length
                    self.rows.loc[self.rows.index.size-1,'N_panel']=np.floor((b6.area+con_area)/(b3.area+con_area)) 
                    self.rows.loc[self.rows.index.size-1,'row_surf']=b6.area   
                    if self.rows.loc[self.rows.index.size-1,'N_panel']>0:
                        
                        b7=affinity.translate(b3,xoff=b6.bounds[0]-b3.bounds[0],
                                              yoff=b6.bounds[3]-b3.bounds[3])
                        b7_xy=pd.DataFrame(b7.boundary.xy).sort_values(by=0,axis=1).T.drop_duplicates().T
                        # ax.plot(*b6.exterior.xy)
                        if self.f_plot==True:
                            ax.plot(*b7.exterior.xy)
                            
                        for z in range(1,int(self.rows.loc[self.rows.index.size-1,'N_panel'])):
                            b8=affinity.translate(b7,xoff=z*((self.l+self.off_pnl)*np.sin(np.radians(self.teta))),
                                              yoff=-z*((self.l+self.off_pnl)*np.cos(np.radians(self.teta))))
                            if self.f_plot==True:
                                ax.plot(*b8.exterior.xy)
                    # ax.plot(*b5.exterior.xy)
                    L_west=L_west.parallel_offset(self.off_row+self.w_loop,side="rigth")
                    L_east=L_east.parallel_offset(self.off_row+self.w_loop,side="rigth")
                    
                    
                # rows=rows.drop(index=rows.index[-1])
                    
                if self.f_plot==True:
                    plt.show()
                self.roof.loc[self.roof.index.size,'N_panel']=self.rows.loc[self.rows.index[-i-1]:,'N_panel'].sum()*2
                self.roof.loc[self.roof.index.size-1,'ratio']=self.roof.loc[self.roof.index.size-1,'N_panel']*self.l*self.w/B1.area
                self.roof.loc[self.roof.index.size-1,'tilt']=self.tilt
                self.roof.loc[self.roof.index.size-1,'cll_azimut']=self.teta+self.conv_orient
                self.roof.loc[self.roof.index.size-1,'row_dist']=self.off_row
            
        else:
            self.off_row=np.max([self.w*math.sin(math.radians(self.tilt))*1/np.tan(math.radians(self.W_S_A)),self.d_rows_min])
            
            if self.teta % 90 ==0:
                if self.teta == -90:
                    b3 = box(B1.bounds[2]-self.w*math.cos(math.radians(self.tilt)), B1.bounds[3]-self.l, 
                             B1.bounds[2], B1.bounds[3])
                    L_south=LineString([(B1.bounds[2], B1.bounds[1]), (B1.bounds[2], B1.bounds[3])]) 
                    L_north=L_south.parallel_offset(self.w*math.cos(math.radians(self.tilt)),side='left')
                    b6= box(b3.bounds[0], b3.bounds[3], 
                             B1.bounds[2], B1.bounds[1])
                    
                elif self.teta == +90:
                    b3 = box(B1.bounds[0], B1.bounds[1], 
                             B1.bounds[0]+self.w*math.cos(math.radians(self.tilt)), B1.bounds[1]+self.l)    
                    L_south=LineString([(B1.bounds[0], B1.bounds[1]), (B1.bounds[0], B1.bounds[3])]) 
                    L_north=L_south.parallel_offset(self.w*math.cos(math.radians(self.tilt)))
                    b6= box(b3.bounds[2], b3.bounds[1], 
                             B1.bounds[0], B1.bounds[3])
                elif self.teta == 0:
                    b3 = box(B1.bounds[0], B1.bounds[3], 
                             B1.bounds[0]+self.l, B1.bounds[3]-self.w*math.cos(math.radians(self.tilt)))    
                    L_south=LineString([(B1.bounds[0], B1.bounds[3]), (B1.bounds[2], B1.bounds[3])]) 
                    L_north=L_south.parallel_offset(self.w*math.cos(math.radians(self.tilt)))
                    b6= box(b3.bounds[0], b3.bounds[1], 
                             B1.bounds[2], B1.bounds[3])
                
                
                con_area=b3.area*self.off_pnl/self.l
                self.rows.loc[self.rows.index.size,'edge_south']=L_south.length
                self.rows.loc[self.rows.index.size-1,'edge_north']=L_north.length
                self.rows.loc[self.rows.index.size-1,'row_surf']=b6.area
                self.rows.loc[self.rows.index.size-1,'N_panel']=np.floor((b6.area+con_area)/(b3.area+con_area)) 
                
                if self.f_plot==True:
                    fig, ax = plt.subplots(figsize=(self.L, self.W))
                    ax.plot(*B.exterior.xy)
                    ax.plot(*B1.exterior.xy)
                    ax.plot(*b3.exterior.xy)
                    
                if self.rows.loc[self.rows.index.size-1,'N_panel']>0:
                    if self.teta==-90:
                        b7=affinity.translate(b3,xoff=b6.bounds[0]-b3.bounds[0],
                                              yoff=b6.bounds[3]-b3.bounds[3])
                    elif self.teta==90:
                        b7=affinity.translate(b3,xoff=b6.bounds[0]-b3.bounds[0],
                                              yoff=b6.bounds[1]-b3.bounds[1])
                    elif self.teta == 0:
                        b7=affinity.translate(b3,xoff=b6.bounds[0]-b3.bounds[0],
                                              yoff=b6.bounds[3]-b3.bounds[3])
                            
                    
                    b7_xy=pd.DataFrame(b7.boundary.xy).sort_values(by=0,axis=1)
                    if self.f_plot==True:
                        ax.plot(*b7.exterior.xy)
                    
                    for z in range(1,int(self.rows.loc[self.rows.index.size-1,'N_panel'])):
                        
                        b8=affinity.translate(b7,xoff=z*(self.l+self.off_pnl)*math.cos(math.radians(self.teta)),
                                          yoff=z*(self.l+self.off_pnl)*math.sin(math.radians(self.teta)))
                        
                        if self.f_plot==True:
                            ax.plot(*b8.exterior.xy)
                while L_north.intersection(B1).length>0:
                    
                    if self.teta==-90:
                        L_south=L_south.parallel_offset(self.off_row+self.w*math.cos(math.radians(self.tilt)),side='left')
                        L_north=L_north.parallel_offset(self.off_row+self.w*math.cos(math.radians(self.tilt)),side='left')
                    elif self.teta == 90:
                        L_south=L_south.parallel_offset(self.off_row+self.w*math.cos(math.radians(self.tilt)))
                        L_north=L_north.parallel_offset(self.off_row+self.w*math.cos(math.radians(self.tilt)))
                    elif self.teta == 0:
                        L_south=L_south.parallel_offset(self.off_row+self.w*math.cos(math.radians(self.tilt)))
                        L_north=L_north.parallel_offset(self.off_row+self.w*math.cos(math.radians(self.tilt)))
                    
                    if L_north.intersection(B1).length>0 :
                        b6=box(L_north.intersection(B1).bounds[0], L_north.intersection(B1).bounds[1],
                               L_south.intersection(B1).bounds[2], L_south.intersection(B1).bounds[3],)
                        b3_xy=pd.DataFrame(b3.boundary.xy).sort_values(by=0,axis=1)
                        b6_xy=pd.DataFrame(b6.boundary.xy).sort_values(by=0,axis=1)
                        
                        self.rows.loc[self.rows.index.size,'edge_south']=L_south.intersection(B1).length
                        self.rows.loc[self.rows.index.size-1,'edge_north']=L_north.intersection(B1).length
                        self.rows.loc[self.rows.index.size-1,'N_panel']=np.floor((b6.area+con_area)/(b3.area+con_area)) 
                        self.rows.loc[self.rows.index.size-1,'row_surf']=b6.area   
                        if self.rows.loc[self.rows.index.size-1,'N_panel']>0:
                            if self.teta==-90:
                                b7=affinity.translate(b3,xoff=b6.bounds[0]-b3.bounds[0],
                                                      yoff=b6.bounds[3]-b3.bounds[3])
                            elif self.teta==90:
                                b7=affinity.translate(b3,xoff=b6.bounds[0]-b3.bounds[0],
                                                      yoff=b6.bounds[1]-b3.bounds[1])
                            elif self.teta == 0:
                                b7=affinity.translate(b3,xoff=b6.bounds[0]-b3.bounds[0],
                                                      yoff=b6.bounds[3]-b3.bounds[3])
                           
                            
                            b7_xy=pd.DataFrame(b7.boundary.xy).sort_values(by=0,axis=1)
                            if self.f_plot==True:
                                ax.plot(*b7.exterior.xy)
                            for z in range(1,int(self.rows.loc[self.rows.index.size-1,'N_panel'])):
                                b8=affinity.translate(b7,xoff=z*(self.l+self.off_pnl)*math.cos(math.radians(self.teta)),
                                                      yoff=(z*(self.l+self.off_pnl)*math.sin(math.radians(self.teta))))
                                if self.f_plot==True:
                                    ax.plot(*b8.exterior.xy)
                if self.f_plot==True:
                    plt.show()
                self.roof.loc[self.roof.index.size,'N_panel']=self.rows.N_panel.sum()
                self.roof.loc[self.roof.index.size-1,'ratio']=self.roof.loc[self.roof.index.size-1,'N_panel']*self.l*self.w/B1.area
                self.roof.loc[self.roof.index.size-1,'tilt']=self.tilt
                self.roof.loc[self.roof.index.size-1,'cll_azimut']=self.teta+self.conv_orient
                self.roof.loc[self.roof.index.size-1,'row_dist']=self.off_row
            elif self.teta < 0:
                b1 = box(B1.bounds[2]-self.l, B1.bounds[1], 
                         B1.bounds[2], B1.bounds[1]+self.w*math.cos(math.radians(self.tilt)))
                
                b2 = affinity.rotate(b1, self.teta, (b1.bounds[2], b1.bounds[3]))
                b3=affinity.translate(b2,xoff=0,
                                      yoff=self.W-self.d_W-b2.bounds[3])
                con_area=b3.area*self.off_pnl/self.l
                b3_xy=pd.DataFrame(b3.boundary.xy).sort_values(by=0,axis=1)
                
                L1=LineString([(B1.bounds[0], B1.bounds[1]), (B1.bounds[2], B1.bounds[1])]) 
                L1=affinity.rotate(L1,self.teta,(B1.bounds[2],B1.bounds[1]))
                L1=affinity.translate(L1,yoff=b3_xy.loc[1,b3_xy.loc[0,:]==b3_xy.loc[0,:].max()]
                                      -B1.bounds[1],xoff=0)
                L1=affinity.scale(L1,xfact=np.max([self.L/self.l,self.W/self.w]),
                                   yfact=np.max([self.L/self.l,self.W/self.w]))
                
                
                
                L_south=L1.parallel_offset(0)
                L_north=L_south.parallel_offset(self.w*math.cos(math.radians(self.tilt)))
                if L_north.intersection(B1).length==self.W:
                    b6= box(b3.bounds[0], b3.bounds[3], 
                             B1.bounds[2], B1.bounds[1])
                else:
                    b6=b3
                
                self.rows.loc[self.rows.index.size,'edge_south']=L_south.intersection(B1).length
                self.rows.loc[self.rows.index.size-1,'edge_north']=L_north.intersection(B1).length
                self.rows.loc[self.rows.index.size-1,'N_panel']=np.floor((b6.area+con_area)/(b3.area+con_area)) 
                self.rows.loc[self.rows.index.size-1,'row_surf']=b6.area
                if self.f_plot==True:
                    fig, ax = plt.subplots(figsize=(self.L, self.W))
                    ax.plot(*B.exterior.xy)
                    ax.plot(*B1.exterior.xy)
                    ax.plot(*b3.exterior.xy)
                    plt.xlim([-self.l, self.L+self.l])
                    plt.ylim([-self.w, self.W+self.w])
                search_bound=L_north.parallel_offset(self.off_row+self.w*math.cos(math.radians(self.tilt)))
                
                while search_bound.intersection(B1).length>0:
                    
                    L_south=L_south.parallel_offset(self.off_row+self.w*math.cos(math.radians(self.tilt)))
                    L_north=L_north.parallel_offset(self.off_row+self.w*math.cos(math.radians(self.tilt)))
                    # ax.plot(*L_south.xy)
                    # ax.plot(*L_north.xy)
                    if L_north.intersection(B1).length>self.l :
                        b4a = box(L_north.intersection(B1).bounds[0], L_north.intersection(B1).bounds[3], 
                                 L_north.intersection(B1).bounds[0]+self.w*math.cos(math.radians(self.tilt)), L_north.intersection(B1).bounds[3]-L_north.intersection(B1).length)
                        b4 = affinity.rotate(b4a,self.teta+90, (L_north.intersection(B1).bounds[0],
                                                            L_north.intersection(B1).bounds[3]))
                                                                                
                        
                        b5b = box(L_south.intersection(B1).bounds[0], L_south.intersection(B1).bounds[3], 
                                 L_south.intersection(B1).bounds[0]-self.w*math.cos(math.radians(self.tilt)), L_south.intersection(B1).bounds[3]-L_south.intersection(B1).length)
                        b5 = affinity.rotate(b5b, self.teta+90, (L_south.intersection(B1).bounds[0],
                                                            L_south.intersection(B1).bounds[3]))
                                                                                
                        # ax.plot(*b4.exterior.xy)
                        # ax.plot(*b5.exterior.xy)
                        try:
                            b6=b4.intersection(b5)
                            b3_xy=pd.DataFrame(b3.boundary.xy).sort_values(by=0,axis=1)
                            b6_xy=pd.DataFrame(b6.boundary.xy).sort_values(by=0,axis=1)
                            
                        except:
                            b6=b5.intersection(b4)
                            b3_xy=pd.DataFrame(b3.boundary.xy).sort_values(by=0,axis=1)
                            b6_xy=pd.DataFrame(b6.boundary.xy).sort_values(by=0,axis=1)
                            
                        
                        self.rows.loc[self.rows.index.size,'edge_south']=L_south.intersection(B1).length
                        self.rows.loc[self.rows.index.size-1,'edge_north']=L_north.intersection(B1).length
                        self.rows.loc[self.rows.index.size-1,'N_panel']=np.floor((b6.area+con_area)/(b3.area+con_area)) 
                        self.rows.loc[self.rows.index.size-1,'row_surf']=b6.area   
                        if self.rows.loc[self.rows.index.size-1,'N_panel']>0:
                            
                            b7=affinity.translate(b3,xoff=b6.bounds[0]-b3.bounds[0],
                                                  yoff=b6.bounds[3]-b3.bounds[3])
                            b7_xy=pd.DataFrame(b7.boundary.xy).sort_values(by=0,axis=1)
                            
                            if self.f_plot==True:
                                ax.plot(*b7.exterior.xy)
                            for z in range(1,int(self.rows.loc[self.rows.index.size-1,'N_panel'])):
                                b8=affinity.translate(b7,xoff=z*((self.l+self.off_pnl)*math.cos(math.radians(self.teta))),
                                                  yoff=z*((self.l+self.off_pnl)*math.sin(math.radians(self.teta))))
                                if self.f_plot==True:
                                    ax.plot(*b8.exterior.xy)
                    search_bound=L_north.parallel_offset(self.off_row+self.w*math.cos(math.radians(self.tilt)))
                if self.f_plot==True:
                    plt.show()
                self.roof.loc[self.roof.index.size,'N_panel']=self.rows.N_panel.sum()
                self.roof.loc[self.roof.index.size-1,'ratio']=self.roof.loc[self.roof.index.size-1,'N_panel']*self.l*self.w/B1.area
                self.roof.loc[self.roof.index.size-1,'tilt']=self.tilt
                self.roof.loc[self.roof.index.size-1,'cll_azimut']=self.teta+self.conv_orient
                self.roof.loc[self.roof.index.size-1,'row_dist']=self.off_row
            elif self.teta>0:
                
                b1 = box(B1.bounds[0], B1.bounds[1], 
                         B1.bounds[0]+self.l, B1.bounds[1]+self.w*math.cos(math.radians(self.tilt)))
                
                b2 = affinity.rotate(b1, self.teta, (b1.bounds[0], b1.bounds[3]))
                b3=affinity.translate(b2,xoff=0,
                                      yoff=self.W-self.d_W-b2.bounds[3])
                b3_xy=pd.DataFrame(b3.boundary.xy).sort_values(by=0,axis=1)
                con_area=b3.area*self.off_pnl/self.l
                L1=LineString([(B1.bounds[0], B1.bounds[1]), (B1.bounds[2], B1.bounds[1])]) 
                L1=affinity.rotate(L1,+self.teta,(B1.bounds[0], B1.bounds[1]))          
                L1=affinity.translate(L1,xoff=0,yoff=b3_xy.iloc[1,0]-
                                      B1.bounds[1])
                L1=affinity.scale(L1,xfact=np.max([self.L/self.l,self.W/self.w]),
                                  yfact=np.max([self.L/self.l,self.W/self.w]))
                L_south=L1.parallel_offset(0)
                L_north=L_south.parallel_offset(self.w*math.cos(math.radians(self.tilt)))
                if L_north.intersection(B1).length==self.W:
                    b6= box(B1.bounds[0], B1.bounds[3],
                            b3.bounds[2], b1.bounds[1])
                else:
                    b6=b3
                
                self.rows.loc[self.rows.index.size,'edge_south']=L_south.intersection(B1).length
                self.rows.loc[self.rows.index.size-1,'edge_north']=L_north.intersection(B1).length
                self.rows.loc[self.rows.index.size-1,'row_surf']=b6.area
                self.rows.loc[self.rows.index.size-1,'N_panel']=np.floor((b6.area+con_area)/(b3.area+con_area)) 
                if self.f_plot==True:
                    fig, ax = plt.subplots(figsize=(self.L, self.W))
                    ax.plot(*B.exterior.xy)
                    ax.plot(*B1.exterior.xy)
                    ax.plot(*b3.exterior.xy)
                    plt.xlim([-self.l, self.L+self.l])
                    plt.ylim([-self.w, self.W+self.w])
                while L_north.intersection(B1).length>0:
                    L_south=L_south.parallel_offset(self.off_row+self.w*math.cos(math.radians(self.tilt)))
                    L_north=L_north.parallel_offset(self.off_row+self.w*math.cos(math.radians(self.tilt)))
                    if L_north.intersection(B1).length>0 :
                        b4a = box(L_north.intersection(B1).bounds[0], L_north.intersection(B1).bounds[1], 
                                 L_north.intersection(B1).bounds[0]+L_north.intersection(B1).length, L_north.intersection(B1).bounds[1]+self.w*1.1*math.cos(math.radians(self.tilt)))
                        b4 = affinity.rotate(b4a, self.teta, (L_north.intersection(B1).bounds[0],
                                                          L_north.intersection(B1).bounds[1]))
                        
                        b5b = box(L_south.intersection(B1).bounds[0], L_south.intersection(B1).bounds[1], 
                                 L_south.intersection(B1).bounds[0]+L_south.intersection(B1).length, L_south.intersection(B1).bounds[1]-self.w*1.1*math.cos(math.radians(self.tilt)))
                        b5 = affinity.rotate(b5b, self.teta, (L_south.intersection(B1).bounds[0],
                                                          L_south.intersection(B1).bounds[1]))
                        try:
                            b6=b5.intersection(b4)
                        except:
                            b6=b4.intersection(b5)
                        b3_xy=pd.DataFrame(b3.boundary.xy).sort_values(by=0,axis=1,ascending=True)
                        b6_xy=pd.DataFrame(b6.boundary.xy).sort_values(by=0,axis=1,ascending=True)
                        
                        self.rows.loc[self.rows.index.size,'edge_south']=L_south.intersection(B1).length
                        self.rows.loc[self.rows.index.size-1,'edge_north']=L_north.intersection(B1).length
                        self.rows.loc[self.rows.index.size-1,'N_panel']=np.floor((b6.area+con_area)/(b3.area+con_area)) 
                        self.rows.loc[self.rows.index.size-1,'row_surf']=b6.area   
                        
                        if self.rows.loc[self.rows.index.size-1,'N_panel']>0:
                            
                            b7=affinity.translate(b3,xoff=b6_xy.iloc[0,0]-b3_xy.iloc[0,0],
                                                  yoff=np.min(b6_xy.iloc[1,:])-np.min(b3_xy.iloc[1,:]))
                            b7_xy=pd.DataFrame(b7.boundary.xy).sort_values(by=0,axis=1)
                            if self.f_plot==True:
                                ax.plot(*b7.exterior.xy)
                            for z in range(1,int(self.rows.loc[self.rows.index.size-1,'N_panel'])):
                                b8=affinity.translate(b7,xoff=np.abs(z*(self.l+self.off_pnl)*math.cos(math.radians(self.teta))),
                                                  yoff=np.abs(z*(self.l+self.off_pnl)*math.sin(math.radians(self.teta))))
                                if self.f_plot==True:
                                    ax.plot(*b8.exterior.xy)
                if self.f_plot==True:
                    plt.show()
                self.roof.loc[self.roof.index.size,'N_panel']=self.rows.N_panel.sum()
                self.roof.loc[self.roof.index.size-1,'ratio']=self.roof.loc[self.roof.index.size-1,'N_panel']*self.l*self.w/B1.area
                self.roof.loc[self.roof.index.size-1,'tilt']=self.tilt
                self.roof.loc[self.roof.index.size-1,'cll_azimut']=self.teta+self.conv_orient
                self.roof.loc[self.roof.index.size-1,'row_dist']=self.off_row
        return None
            
        
if __name__ == "__main__":   
    for item in [190]:
        for L,W in [[50,20]]:
            for tilt in [20,30,40]:
                try: 
                    meteo=Calpinage_light(orientation=item,lat=46.5098019,long=6.6617476,tilt=20, 
                                 W=10,L=10,w=1,l=2.05,d_W=0.5,d_L=0.5,
                                 tilt_EW=20,f_EW=False,f_plot=False,d_rows=0.6,
                                 parallel="short",optimal=True)
                    row=meteo.rows
                    roof=meteo.roof
                    print(item)
                    # print(row)    
                    print(roof)
                    print('PAUSE')
                    # meteo=Calpinage(orientation=item,W=20,L=50,tilt=15,f_EW=True, f_plot=True,f_orient=True)
                    # row=meteo.rows
                    # roof=meteo.roof
                    # print(item)
                    # # print(row)    
                    # print(roof)
                    # print('PAUSE')
                    # meteo=Calpinage(orientation=item,W=20,L=50,tilt=15,f_EW=False, f_plot=True,f_orient=False)
                    # row=meteo.rows
                    # roof=meteo.roof
                    # print(item)
                    # # print(row)    
                    # print(roof)
                    # print('PAUSE')
                except:
                    pass


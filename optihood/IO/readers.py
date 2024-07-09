import configparser as _cp
import csv as _csv
import dataclasses as _dc
import pathlib as _pl

import pandas as _pd

import optihood.entities as _ent


@_dc.dataclass
class CsvReader:
    # add quoting flag according to possibilities.
    dir_path: _pl.Path

    # quoting_flag: [_csv.QUOTE_NONNUMERIC, _csv.QUOTE_NONE, _csv.QUOTE_ALL, _csv.QUOTE_MINIMAL, _csv.QUOTE_STRINGS,
    # _csv.QUOTE_NOTNULL]

    def read(self, file_name: str) -> _pd.DataFrame:
        # read_csv does not have as strong a parser as ExcelFile.parse.
        # One issue the following addresses, is the "nr as string" outputs.

        df = _pd.read_csv(self.dir_path / file_name)
        for column in df.columns:
            self.make_nrs_numeric(df, column)

        return df

    @staticmethod
    def make_nrs_numeric(df: _pd.DataFrame, column_name: str) -> None:
        # Fix using "coerce" and re-filling NaN values.
        # Unfortunately, this applies to full text columns as well.

        if df[column_name].dtype == object:
            series_old = df[column_name].copy(deep=True)
            df[column_name] = df[column_name].apply(_pd.to_numeric, errors="coerce")
            nan_map = df[column_name].isna()
            df[column_name][nan_map] = series_old[nan_map]


@_dc.dataclass
class CsvScenarioReader(CsvReader):
    """Very simplified implementation.
    Each CSV file inherently has its own data model.
    This needs to be incorporated into a validation of these inputs.
    """

    relative_file_paths: dict[str, str] = _dc.field(init=False)

    def __post_init__(self):
        self.relative_file_paths = {
            _ent.NodeKeys.buses: "buses.csv",
            _ent.NodeKeys.grid_connection: "grid_connection.csv",
            _ent.NodeKeys.commodity_sources: "commodity_sources.csv",
            _ent.NodeKeys.solar: "solar.csv",
            _ent.NodeKeys.transformers: "transformers.csv",
            _ent.NodeKeys.demand: "demand.csv",
            _ent.NodeKeys.storages: "storages.csv",
            _ent.NodeKeys.stratified_storage: "stratified_storage.csv",
            _ent.NodeKeys.profiles: "profiles.csv",
        }

    def read_scenario(self) -> dict[str, _pd.DataFrame]:
        data = {}
        errors = []
        for key, rel_path in self.relative_file_paths.items():
            try:
                data[key] = self.read(rel_path)
                # df_current = _pd.read_csv(path)
            except FileNotFoundError as e:
                errors.append(e)

            # validation_error = self.validate(key, df_current)
            # if not validation_error:
            #     data[key] = df_current
            # else:
            #     errors.append(validation_error)

        if errors:
            raise ExceptionGroup("Issues with CSV files.", errors)

        return data


def parse_config(configFilePath: str):
    # Making this a class method would allow us to provide the parser.
    config = _cp.ConfigParser()
    config.read(configFilePath)
    configData = {}
    for section in config.sections():
        configData[section] = config.items(section)
    configData = {k.lower(): v for k, v in configData.items()}

    return configData

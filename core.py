from __future__ import annotations

from dataclasses import dataclass

import arcpy

from consts import FileNames
import csv
import os


def check_na_or_empty(s: str, default):
    if s == "" or s == "N.A.":
        return default
    return s


@dataclass
class SportFacility:
    gmid: str
    dataset: str
    fac_name: str
    addr: str | None
    district: str | None
    northing: float
    easting: float
    lat: float
    lon: float

    @classmethod
    def from_csv_row(cls, csv_row: list[str]):
        return cls(
            csv_row[0],
            csv_row[1],
            csv_row[2],
            check_na_or_empty(csv_row[3], None),
            check_na_or_empty(csv_row[4], None),
            float(csv_row[5]),
            float(csv_row[6]),
            float(csv_row[7]),
            float(csv_row[8]),
        )


def read_all_csvs(folder: str) -> list[SportFacility]:
    """
    :param folder: folder containing the csv files
    :return: a list merging all the csv files in the directory
    """
    table = []
    for filename in FileNames:
        table.extend(read_csv(os.path.join(folder, filename)))
    return table


def read_csv(filename) -> list[SportFacility]:
    """
    :param filename: path to the csv
    :return: a list of csv rows
    """
    with open(filename, encoding='utf-8') as f:
        csv_reader = csv.reader(f)
        next(csv_reader)  # skip the header
        return [SportFacility.from_csv_row(row) for row in csv_reader]


def exception_handler(f):
    """
    A decorator to try the inner function
    :param f: A function that might raise arcpy.ExecuteError
    :return: A wrapper function that calls the inner function, catching ExecuteError and Exception before
             re-raising the exception
    """
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except arcpy.ExecuteError:
            # Access the __name__ attribute to get the function name
            print(f"Error while running {f.__name__}(): {arcpy.GetMessages()}")
            raise
        except Exception as e:
            print(f"Unexpected error while running {f.__name__}: {e}")
            raise
    return wrapper


def replace_special_chars(name: str) -> str:
    return (
        name.replace(' ', '_')
        .replace('&', "and")
        .replace(',', "")
    )

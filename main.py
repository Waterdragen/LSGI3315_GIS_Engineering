from core import read_all_csvs
from pprint import pprint

def read_csv():
    sports_data = read_all_csvs("./csv_data/")
    pprint(sports_data)

def main():
    read_csv()

if __name__ == "__main__":
    main()

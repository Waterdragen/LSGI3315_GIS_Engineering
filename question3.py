import multiprocessing as mp
import os
from itertools import combinations
import shutil

import arcpy
import arcpy.conversion
import arcpy.management

from consts import FacilityTypes, WORKSPACE
from core import read_all_csvs, exception_handler, replace_special_chars

try:
    arcpy.CreateFileGDB_management("./", WORKSPACE)
except arcpy.ExecuteError:
    pass

arcpy.env.workspace = WORKSPACE
arcpy.env.overwriteOutput = True
geo_feature_counter = 0

# Set coordinate system to Hong Kong 1980 Grid (EPSG:2326)
HK1980GRID = arcpy.SpatialReference(2326)
arcpy.env.outputCoordinateSystem = HK1980GRID

if not os.path.exists("./shape"):
    os.makedirs("./shape")

def make_fac_type_layer(feature_class, facility_type):
    # Create a new feature layer for the current facility type
    fac_type_name = f"{replace_special_chars(facility_type)}_Layer"
    fac_type_layer = arcpy.management.SelectLayerByAttribute(
        feature_class, "NEW_SELECTION",
        f"Facility_Type = '{facility_type}'"
    )
    count = int(arcpy.GetCount_management(fac_type_layer)[0])
    print(f"Selected {count} features for Facility_Type = '{facility_type}'")

    print(f"Created layer {fac_type_name}")
    arcpy.CopyFeatures_management(fac_type_layer, f"./shape/{fac_type_name}.shp")


@exception_handler
def three_or_above_facilities(radius: float = 500.0, facilities_list="facilities_list"):
    facilities_buffer = "facilities_buffer"
    three_type_fac_intersect = "ThreeTypeIntersect"
    hk_shape = "./Hong_Kong_18_Districts/HKDistrict18.shp"
    arcpy.Buffer_analysis(facilities_list, facilities_buffer, f"{radius} Meters")

    for fac_type in FacilityTypes:
        make_fac_type_layer(facilities_buffer, fac_type)

    # Use multiprocessing for each combination of 3 for the intersection
    with mp.Pool() as pool:
        results = [pool.apply_async(process_combination,
                                    args=(index, fac_type_comb))
                   for index, fac_type_comb
                   in enumerate(combinations(FacilityTypes, 3))]
        fac_intersect_list = [res.get() for res in results]

    # Combine the interecting shapes
    arcpy.management.Merge(fac_intersect_list, three_type_fac_intersect)
    arcpy.Clip_analysis(three_type_fac_intersect, hk_shape)

    # Remove the produced shapes
    shutil.rmtree("./shape/")

    # Dissolve all the shapes into one shape
    temp_name = three_type_fac_intersect + "_temp"
    arcpy.Dissolve_management(three_type_fac_intersect, temp_name)
    arcpy.Delete_management(three_type_fac_intersect)
    arcpy.Rename_management(temp_name, three_type_fac_intersect)

    arcpy.MultipartToSinglepart_management(three_type_fac_intersect, temp_name)
    arcpy.Delete_management(three_type_fac_intersect)
    arcpy.Rename_management(temp_name, three_type_fac_intersect)

    print(f"Successfully saved to {three_type_fac_intersect}")


def process_combination(index, fac_type_comb):
    fac_type_layers = []
    for fac_type in fac_type_comb:
        fac_type_name = f"./shape/{replace_special_chars(fac_type)}_Layer.shp"
        assert arcpy.Exists(fac_type_name), fac_type_name
        fac_type_layers.append(fac_type_name)

    out_name = f"./shape/FeatureCombination_{index}.shp"
    try:
        arcpy.Intersect_analysis(fac_type_layers, out_name, "ONLY_FID")
    except Exception as e:
        print(e)
        print(f"Warning: {out_name} is ignored")
    return out_name


@exception_handler
def main():
    """
    Main function for Task 3
    """
    # Read CSV data
    csv_folder = "./csv_data/"

    if not os.path.exists(csv_folder):
        raise FileNotFoundError(f"CSV folder '{csv_folder}' not found.")

    sports_data = read_all_csvs(csv_folder)

    if not sports_data:
        raise ValueError("No facility data loaded from CSV files.")

    # Question 3: Which areas have a good coverage of different types of sports and outdoor facilities
    # (e.g., equal or more than three types).
    three_or_above_facilities(radius=500.0, facilities_list="facilities_list")


if __name__ == "__main__":
    # Check and checkout Spatial Analyst extension
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
        main()
        arcpy.CheckInExtension("Spatial")

    else:
        print("Error: Spatial Analyst extension is not available.")

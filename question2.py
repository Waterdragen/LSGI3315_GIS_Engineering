import arcpy
from arcpy import analysis
from arcpy import management
from arcpy import env
import os
from core import read_all_csvs, exception_handler
from consts import WORKSPACE
from question1 import create_feature_class

# Set ArcGIS workspace
env.workspace = WORKSPACE
env.overwriteOutput = True  # Allow overwriting existing files

# Set coordinate system to Hong Kong 1980 Grid (EPSG:2326)
SPATIAL_REFERENCE = arcpy.SpatialReference(2326)
env.outputCoordinateSystem = SPATIAL_REFERENCE

# Path to the district shapefile
district_shp = os.path.abspath("./Hong_Kong_18_Districts/HKDistrict18.shp")


def create_buffer(input_fc, buffer_distance, output_fc, dissolve_option="ALL"):
    """
    Create a buffer around the input feature class.

    Args:
        input_fc: Input feature class (e.g., facilities)
        buffer_distance: Buffer distance in meters (e.g., "500 Meters")
        output_fc: Name of the output buffer feature class
        dissolve_option: "ALL" to merge overlapping buffers, "NONE" to keep separate
    Returns:
        Path to the created buffer feature class
    """
    try:
        output_buffer = os.path.join(WORKSPACE, output_fc)
        arcpy.analysis.Buffer(input_fc, output_buffer, buffer_distance, dissolve_option=dissolve_option)
        print(f"Buffer created: '{output_buffer}' with distance {buffer_distance}")
        return output_buffer
    except arcpy.ExecuteError:
        print(f"Error creating buffer: {arcpy.GetMessages()}")
        raise
    except Exception as e:
        print(f"Unexpected error in create_buffer: {e}")
        raise


@exception_handler
def analyze_coverage(facility_fc, district_fc, facility_type, walk_distance, user_distance):
    """
    Analyze areas within walking distance and user-specified distance from facilities.

    Args
        facility_fc: Feature class with all facilities
        district_fc: Feature class with district boundaries
        facility_type: Type of facility (e.g., 'Badminton Court')
        walk_distance: Walking distance in meters (e.g., 500)
        user_distance: User-specified distance in meters (e.g., 1000)
    """
    # Check if district_fc exists
    if not arcpy.Exists(district_fc):
        raise ValueError(f"The district feature class '{district_fc}' does not exist in the geodatabase.")

    # Select facilities of the specified type
    query = f"Facility_Type = '{facility_type}'"
    arcpy.management.SelectLayerByAttribute(facility_fc, "NEW_SELECTION", query)
    if int(arcpy.management.GetCount(facility_fc)[0]) == 0:
        print(f"No features found for '{facility_type}'. Aborting analysis.")
        return

    # Create buffers
    walk_buffer = create_buffer(facility_fc, f"{walk_distance} Meters",
                                f"{facility_type.replace(' ', '_')}_Walk_Buffer")
    user_buffer = create_buffer(facility_fc, f"{user_distance} Meters",
                                f"{facility_type.replace(' ', '_')}_User_Buffer")

    # Intersect buffers with districts
    walk_intersect = os.path.join(WORKSPACE, f"{facility_type.replace(' ', '_')}_Walk_Intersect")
    user_intersect = os.path.join(WORKSPACE, f"{facility_type.replace(' ', '_')}_User_Intersect")
    arcpy.analysis.Intersect([walk_buffer, district_fc], walk_intersect)
    arcpy.analysis.Intersect([user_buffer, district_fc], user_intersect)

    # Calculate coverage percentage using ENAME and SHAPE_Area
    arcpy.management.AddField(walk_intersect, "Walk_Coverage_Pct", "DOUBLE")
    arcpy.management.AddField(user_intersect, "User_Coverage_Pct", "DOUBLE")

    # Store original district areas in a dictionary for efficiency
    district_areas = {}
    with arcpy.da.SearchCursor(district_fc, ["ENAME", "SHAPE_Area"]) as cursor:
        for row in cursor:
            district_areas[row[0]] = row[1]

    # Calculate coverage areas and percentages for walk buffer
    with arcpy.da.UpdateCursor(walk_intersect, ["SHAPE@", "Walk_Coverage_Pct", "ENAME"]) as cursor:
        for row in cursor:
            area = row[0].getArea("GEODESIC", "SQUAREMETERS")
            if row[2] in district_areas:
                row[1] = (area / district_areas[row[2]]) * 100
                cursor.updateRow(row)

    # Calculate coverage areas and percentages for user buffer
    with arcpy.da.UpdateCursor(user_intersect, ["SHAPE@", "User_Coverage_Pct", "ENAME"]) as cursor:
        for row in cursor:
            area = row[0].getArea("GEODESIC", "SQUAREMETERS")
            if row[2] in district_areas:
                row[1] = (area / district_areas[row[2]]) * 100
                cursor.updateRow(row)

    print(f"Coverage analysis completed for '{facility_type}'.")
    print(f"Walking distance ({walk_distance} m) results: {walk_intersect}")
    print(f"User-specified distance ({user_distance} m) results: {user_intersect}")


def main():
    """Main function to import districts and analyze facility accessibility."""
    try:
        # Define the district feature class
        district_fc = os.path.join(WORKSPACE, "Hong_Kong_18_Districts")

        # Check if the district feature class exists; if not, import the shapefile
        if not arcpy.Exists(district_fc):
            arcpy.conversion.FeatureClassToFeatureClass(district_shp, WORKSPACE, "Hong_Kong_18_Districts")
            print(f"Imported 'Hong_Kong_18_Districts' into {WORKSPACE}")
        else:
            print("'Hong_Kong_18_Districts' already exists in the geodatabase.")

        # List all districts and their areas using ENAME and SHAPE_Area
        print("\nDistricts in Hong Kong and their areas:")
        with arcpy.da.SearchCursor(district_fc, ["ENAME", "SHAPE_Area"]) as cursor:
            for row in cursor:
                print(f"District: {row[0]}, Area: {row[1]} square units")

        # Read CSV data
        csv_folder = "./csv_data/"  # Update this path to your actual CSV folder
        if not os.path.exists(csv_folder):
            raise FileNotFoundError(f"CSV folder '{csv_folder}' not found.")
        sports_data = read_all_csvs(csv_folder)
        if not sports_data:
            raise ValueError("No facility data loaded from CSV files.")

        # Create facility feature class using the imported function from Task1
        facility_fc = create_feature_class(sports_data, "facilities_list")

        # User inputs for analysis
        facility_type = "Badminton Court"  # Example facility type
        walk_distance = 500  # Walking distance in meters
        user_distance = 1000  # User-specified distance in meters

        # Perform coverage analysis
        analyze_coverage(facility_fc, district_fc, facility_type, walk_distance, user_distance)

    except Exception as e:
        print(f"Error in main: {e}")
    finally:
        print("\nAll tasks completed successfully.")


if __name__ == "__main__":
    # Check and checkout Spatial Analyst extension
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
        main()
        arcpy.CheckInExtension("Spatial")
    else:
        print("Error: Spatial Analyst extension is not available.")
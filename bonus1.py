import arcpy
import arcpy.management
import os
import re  # Added for regular expression cleaning
from geopy.distance import geodesic

from core import read_all_csvs
from consts import WORKSPACE

# Set ArcGIS workspace
arcpy.env.workspace = WORKSPACE
arcpy.env.overwriteOutput = True  # Allow overwriting existing files

# Set coordinate system to Hong Kong 1980 Grid (EPSG:2326)
SPATIAL_REFERENCE = arcpy.SpatialReference(2326)
arcpy.env.outputCoordinateSystem = SPATIAL_REFERENCE

# PolyU coordinates (latitude, longitude)
POLYU_LAT = 22.301612
POLYU_LON = 114.184546

# Walkable distance threshold in kilometers
WALKABLE_DISTANCE_KM = 1.0  # Adjust as needed (e.g., 0.5 km for a shorter range)

def filter_facilities_by_type_and_distance(sports_data, lat, lon, distance_km):
    """
    Filter facilities by type and within a specified distance from a reference point.

    Args:
        sports_data (list): List of SportFacility objects from CSV files.
        lat (float): Latitude of the reference point (e.g., PolyU).
        lon (float): Longitude of the reference point (e.g., PolyU).
        distance_km (float): Distance threshold in kilometers.

    Returns:
        dict: Dictionary with facility types as keys and lists of facilities as values.
    """
    filtered_by_type = {}
    for facility in sports_data:
        facility_coords = (facility.lat, facility.lon)
        polyu_coords = (lat, lon)
        distance = geodesic(facility_coords, polyu_coords).kilometers
        if distance <= distance_km:
            # Extract and format facility type from dataset
            facility_type = facility.dataset.replace(".csv", "").replace("_", " ").title()
            if facility_type not in filtered_by_type:
                filtered_by_type[facility_type] = []
            filtered_by_type[facility_type].append(facility)
    return filtered_by_type

def create_feature_class_for_type(facility_type, filtered_data, output_fc_name):
    """
    Create a point feature class for a specific facility type.

    Args:
        facility_type (str): Name of the facility type (e.g., "Basketball Court").
        filtered_data (list): List of facilities for that type.
        output_fc_name (str): Name of the output feature class.

    Returns:
        str: Path to the created feature class.
    """
    try:
        # Create a new point feature class
        output_fc = arcpy.management.CreateFeatureclass(
            WORKSPACE, output_fc_name, "POINT", spatial_reference=SPATIAL_REFERENCE
        )
        # Add fields for facility attributes
        arcpy.management.AddField(output_fc, "Facility_Type", "TEXT", field_length=50)
        arcpy.management.AddField(output_fc, "Fac_Name", "TEXT", field_length=100)
        arcpy.management.AddField(output_fc, "District", "TEXT", field_length=50)
        # Insert data into the feature class
        with arcpy.da.InsertCursor(output_fc, ["SHAPE@", "Facility_Type", "Fac_Name", "District"]) as cursor:
            for facility in filtered_data:
                point = arcpy.Point(facility.easting, facility.northing)
                point_geom = arcpy.PointGeometry(point, SPATIAL_REFERENCE)
                cursor.insertRow([point_geom, facility_type, facility.fac_name, facility.district])
        print(f"Feature class '{output_fc}' for '{facility_type}' created successfully.")
        return output_fc
    except arcpy.ExecuteError:
        print(f"Error creating feature class for '{facility_type}': {arcpy.GetMessages()}")
        raise
    except Exception as e:
        print(f"Unexpected error for '{facility_type}': {e}")
        raise

def main():
    """Main function to classify facilities by type and create feature classes."""
    try:
        # Step 1: Read CSV data
        csv_folder = "./csv_data/"  # Update to your CSV folder path
        if not os.path.exists(csv_folder):
            raise FileNotFoundError(f"CSV folder '{csv_folder}' not found.")
        sports_data = read_all_csvs(csv_folder)
        if not sports_data:
            raise ValueError("No facility data loaded from CSV files.")
        # Step 2: Filter facilities by type and distance from PolyU
        filtered_by_type = filter_facilities_by_type_and_distance(
            sports_data, POLYU_LAT, POLYU_LON, WALKABLE_DISTANCE_KM
        )
        if not filtered_by_type:
            print("No facilities found within the walkable distance for any type.")
            return
        # Step 3: Create a feature class for each facility type
        for facility_type, facilities in filtered_by_type.items():
            # Clean facility_type for feature class name to remove invalid characters
            fc_name_clean = re.sub(r'[^a-zA-Z0-9]+', '_', facility_type)
            output_fc_name = f"{fc_name_clean}_Near_PolyU"
            create_feature_class_for_type(facility_type, facilities, output_fc_name)
    except Exception as e:
        print(f"Error in main: {e}")

if __name__ == "__main__":
    main()
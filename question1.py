import arcpy
import arcpy.management
from arcpy import env
from arcpy.sa import PointDensity, NbrCircle
import os
from math import pi, sqrt

from core import read_all_csvs, exception_handler
from consts import FileNames, WORKSPACE

if not os.path.exists(WORKSPACE):
    arcpy.CreateFileGDB_management("./", WORKSPACE)

# Set ArcGIS workspace (update this to your actual geodatabase path)
env.workspace = WORKSPACE
env.overwriteOutput = True  # Allow overwriting existing files

# Set coordinate system to Hong Kong 1980 Grid (EPSG:2326)
SPATIAL_REFERENCE = arcpy.SpatialReference(2326)
env.outputCoordinateSystem = SPATIAL_REFERENCE


@exception_handler
def create_feature_class(sports_data, output_fc_name):
    """
    Convert a list of SportFacility objects into an ArcGIS point feature class.

    Args:
        sports_data: List of SportFacility objects from read_all_csvs
        output_fc_name: Name of the output feature class
    Returns:
        Path to the created feature class
    """

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
        for facility in sports_data:
            # Validate coordinates
            if not (facility.easting and facility.northing):
                print(f"Warning: Skipping {facility.fac_name} due to missing coordinates.")
                continue

            point = arcpy.Point(float(facility.easting), float(facility.northing))
            point_geom = arcpy.PointGeometry(point, SPATIAL_REFERENCE)

            facility_type = facility.dataset.replace("_", " ").title()
            cursor.insertRow([point_geom, facility_type, facility.fac_name, facility.district])

    print(f"Feature class '{output_fc}' created successfully.")

    return output_fc


def generate_density_map(facility_type, feature_class, output_file_name, cell_size):
    """
    Generate a density heatmap for a specific facility type.

    Args:
        facility_type: Type of facility (e.g., 'Badminton Court')
        feature_class: Input feature class with all facilities
        output_file_name: Name of the output raster
        cell_size: Raster cell size in meters (default: 100)
    """

    try:
        # Select facilities of the specified type
        query = f"Facility_Type = '{facility_type}'"

        arcpy.management.SelectLayerByAttribute(feature_class, "NEW_SELECTION", query)

        # Check if any features were selected
        if int(arcpy.management.GetCount(feature_class)[0]) == 0:
            print(f"Warning: No features found for '{facility_type}'. Skipping density map.")
            return

        # Calculate point density
        out_density = PointDensity(feature_class, "NONE", cell_size, area_unit_scale_factor="SQUARE_KILOMETERS")
        out_density.save(output_file_name)
        print(f"Density heatmap for '{facility_type}' saved as '{output_file_name}'.")

    except arcpy.ExecuteError:
        print(f"Error generating density map for '{facility_type}': {arcpy.GetMessages()}")
    except Exception as e:
        print(f"Unexpected error in generate_density_map: {e}")


@exception_handler
def generate_all_facilities_density_map(feature_class, output_file_name, cell_size=100):
    """
    Generate a combined density heatmap for all facilities.

    Args:
        feature_class: Input feature class with all facilities
        output_file_name: Name of the output raster
        cell_size: Raster cell size in meters (default: 100)
    """
    # Clear selection to include all facilities
    arcpy.management.SelectLayerByAttribute(feature_class, "CLEAR_SELECTION")

    out_density = PointDensity(feature_class, "NONE", cell_size, area_unit_scale_factor="SQUARE_KILOMETERS")
    out_density.save(output_file_name)

    print(f"Combined density heatmap saved as '{output_file_name}'.")


@exception_handler
def main():
    """Main function to generate heatmaps for sports facilities."""

    # Step 1: Read CSV data
    csv_folder = "./csv_data/"

    if not os.path.exists(csv_folder):
        raise FileNotFoundError(f"CSV folder '{csv_folder}' not found.")

    sports_data = read_all_csvs(csv_folder)

    if not sports_data:
        raise ValueError("No facility data loaded from CSV files.")

    # Step 2: Create feature class
    feature_class = create_feature_class(sports_data, "facilities_list")

    # Step 3: Define facility types from FileNames
    facility_types = [f.replace(".csv", "").replace("_", " ").title() for f in FileNames]

    # Step 4: Generate density heatmap for each facility type
    for facility_type in facility_types:
        output_name = f"{facility_type.replace(' ', '_')}_Density"

        generate_density_map(facility_type, feature_class, output_name, cell_size=100)

    # Step 5: Generate combined density heatmap

    generate_all_facilities_density_map(feature_class, "All_Facilities_Density", cell_size=100)


if __name__ == "__main__":
    # Check and checkout Spatial Analyst extension
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
        main()
        arcpy.CheckInExtension("Spatial")
    else:
        print("Error: Spatial Analyst extension is not available.")
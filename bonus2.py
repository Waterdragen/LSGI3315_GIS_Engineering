import arcpy
import arcpy.management
import arcpy.sa
import os

from core import exception_handler
from consts import WORKSPACE

# Set the workspace to the root directory
arcpy.env.workspace = WORKSPACE
arcpy.env.overwriteOutput = True
HK1980GRID = arcpy.SpatialReference(2326)
arcpy.env.outputCoordinateSystem = HK1980GRID

HKDTM_ASC = os.path.abspath("./HKDTM/DTM.ASC")
HK_DISTRICT_18 = os.path.abspath("./Hong_Kong_18_Districts/HKDistrict18.shp")

@exception_handler
def four_facilities_with_flat_land():
    """
    Find areas with low SD in height and at least 4 facilities (>3)
    """

    dtm_raster = "HK_DTM_5m"
    arcpy.ASCIIToRaster_conversion(HKDTM_ASC, dtm_raster, "FLOAT")

    print(f"Successfully converted {HKDTM_ASC} to raster: {dtm_raster}")

    land_raster = "LandOnly"
    temp_land_raster = "TempLand"

    arcpy.PolygonToRaster_conversion(
        HK_DISTRICT_18,
        "FID",
        temp_land_raster,
        "CELL_CENTER",
        cellsize=50,
    )

    arcpy.env.workspace = WORKSPACE

    # Create a binary mask (1 for land, NoData for water)
    land_mask = arcpy.sa.Con(arcpy.sa.IsNull(temp_land_raster) == 0, 1)

    masked_raster = arcpy.sa.SetNull(land_mask == 0, dtm_raster)
    masked_raster.save(land_raster)

    arcpy.Delete_management(temp_land_raster)

    output_suitable_areas = "FlatArea"
    facilities_fc = "facilities_list"

    neighborhood = arcpy.sa.NbrCircle(500, "MAP")  # 500m radius circle
    elevation_std = arcpy.sa.FocalStatistics(
        land_raster,
        neighborhood,
        "STD",
        "DATA"
    )

    # Step 2: Identify low-variation areas (e.g., std < 2 meters)
    low_variation = arcpy.sa.Con(elevation_std < 20, 1, 0)

    # Step 3: Calculate facility density
    facility_density = arcpy.sa.PointDensity(
        facilities_fc,
        population_field=None,  # No population field
        cell_size=100,  # Pixel size is 100x100 meters
    )

    # Step 4: Identify areas with facilities (density > 3, at least 4 facilities)
    has_facilities = arcpy.sa.Con(facility_density > 3, 1, 0)

    # Step 5: Combine low-variation and facility areas
    suitable_areas = arcpy.sa.Con(
        (low_variation == 1) & (has_facilities == 1), 1, 0
    )

    masked_raster = arcpy.sa.SetNull(suitable_areas == 0, dtm_raster)
    masked_raster.save(output_suitable_areas)

    # Delete the temporary files
    arcpy.Delete_management(dtm_raster)
    arcpy.Delete_management(land_raster)

    print(f"Successfully created suitable areas raster: {output_suitable_areas}")

def main():
    four_facilities_with_flat_land()

if __name__ == "__main__":
    arcpy.CheckOutExtension("Spatial")
    main()

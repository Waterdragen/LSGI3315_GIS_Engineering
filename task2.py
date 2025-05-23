# Waterdragen
# This part is for individual

from __future__ import annotations

import arcpy
import arcpy.conversion
import arcpy.management
import os

from core import SportFacility, read_all_csvs
from consts import WORKSPACE
from collections import Counter
from math import sqrt

HK1980GRID = arcpy.SpatialReference(2326)
arcpy.env.outputCoordinateSystem = HK1980GRID
arcpy.env.overwriteOutput = True

HK_DISTRICT_18 = os.path.abspath("./Hong_Kong_18_Districts/HKDistrict18.shp")
SQM_TO_SQKM = 1_000_000


class FacilityFeature:
    def __init__(self, workspace, csv_folder: str, feature_name: str):
        # Store the workspace for processing data
        self.workspace = workspace
        arcpy.env.workspace = self.workspace
        arcpy.env.overwriteOutput = True
        arcpy.CreateFileGDB_management("./", workspace)

        # Storages for facility and population data
        self.fac_list: list[SportFacility] = read_all_csvs(csv_folder)
        self.feature_name = feature_name

    def point_to_feature_class(self):
        # Set the workspace for processing data
        arcpy.env.workspace = self.workspace

        # Allocate exact space for storing the points to avoid memory overhead
        crs_point_geom: list = [None] * len(self.fac_list)

        for index, facility in enumerate(self.fac_list):
            temp_point = arcpy.Point(X=facility.easting, Y=facility.northing, ID=index)

            geom = arcpy.PointGeometry(temp_point, spatial_reference=HK1980GRID)

            crs_point_geom[index] = geom

        print(f"The out feature name is `{self.feature_name}`")
        arcpy.CopyFeatures_management(crs_point_geom, self.feature_name)
        print("Successfully created a point feature class")

    def add_attribute(self):
        # Set the workspace for processing data
        arcpy.env.workspace = self.workspace
        (FieldManager(self.feature_name)
         .add_field("GMID", "TEXT")
         .add_field("Dataset", "TEXT")
         .add_field("FacilityName", "TEXT")
         .add_field("Address", "TEXT")
         .add_field("District", "TEXT")
         .add_field("Northing", "DOUBLE")
         .add_field("Easting", "DOUBLE")
         .add_field("Latitude", "DOUBLE")
         .add_field("Longitude", "DOUBLE")
         )

        feature_table = arcpy.UpdateCursor(self.feature_name)
        for row, facility in zip(feature_table, self.fac_list):
            row.setValue("GMID", facility.gmid)
            row.setValue("Dataset", facility.dataset)
            row.setValue("FacilityName", facility.fac_name)
            row.setValue("Address", facility.addr)
            row.setValue("District", facility.district)
            row.setValue("Northing", facility.northing)
            row.setValue("Easting", facility.easting)
            row.setValue("Latitude", facility.lat)
            row.setValue("Longitude", facility.lon)
            feature_table.updateRow(row)

        print(f"Successfully added attributes for '{self.feature_name}'")

    # Compulsory Task
    def nearest_facility(self, out_name: str, location: tuple[float, float]):
        """
        Find the location of the nearest facility with a given location.

        Args:
            out_name: the facility name to be saved
            location: (x, y) of the location
        """
        # Set the workspace for processing data
        arcpy.env.workspace = self.workspace

        loc_lat, loc_lon = location

        # Create a point object and its geometry
        point = arcpy.Point(X=loc_lon, Y=loc_lat, ID=1)
        point_geom = arcpy.PointGeometry(point, spatial_reference=HK1980GRID)

        arcpy.SpatialJoin_analysis(point_geom, self.feature_name, out_name,
                                   join_operation="JOIN_ONE_TO_ONE",
                                   match_option="CLOSEST_GEODESIC")
        print(f"Successfully found the nearest facility to point ({loc_lat}, {loc_lon})")
        print(f"Saved as {out_name}\n")

    # Extra questions
    def sport_fac_per_people_per_area(self):
        """
        Computes the sport facilities per 1000 people per square kilometer and saves the feature class.
        """

        print("Computing sport facilities per 1000 people per sq km...")
        population_fc = os.path.abspath("./HK_Population/Pop_Projection_2023to2031.shp")
        output_name = self.feature_name + "_pop_density"

        # Step 1: Read the shape file into the database
        population_fc = arcpy.conversion.FeatureClassToFeatureClass(
            population_fc,
            out_path=WORKSPACE,
            out_name="Hk_Pop_Projection"
        )

        field_name = "fac_density"
        arcpy.management.AddField(population_fc, field_name, "DOUBLE")

        with arcpy.da.UpdateCursor(population_fc,
                                   ["SHAPE@", "Y2025", "Shape_Area", field_name]) as cursor:
            # Step 2: Iterate all the districts (shapes) in the shape file, reading its fields
            for row in cursor:
                # Skip if population or area is zero/null
                shape, population, area_sqm, _ = row
                if not all((population, area_sqm, population)):
                    row[3] = 0
                    cursor.updateRow(row)
                    continue

                # Step 3: Select the facilities contained by the shape
                arcpy.management.SelectLayerByLocation(
                    shape, "CONTAINS", self.feature_name
                )

                # Step 4: Count the facilities selected
                facility_count = int(arcpy.management.GetCount(self.feature_name)[0])

                # Step 5: Calculate density (facilities per 1000 people per sq km)
                # Formula: (facilities / (population/1000)) / (area_sqm/sqm_to_sqkm)
                area_sqkm = area_sqm / SQM_TO_SQKM
                pop_per_thousand = population / 1000

                if pop_per_thousand > 0 and area_sqkm > 0:
                    density = (facility_count / pop_per_thousand) / area_sqkm
                else:
                    density = 0

                row[3] = density
                cursor.updateRow(row)

        # Step 6: Rasterize the polygons
        arcpy.conversion.PolygonToRaster(
            in_features=population_fc,
            value_field=field_name,
            out_rasterdataset=output_name,
            cell_assignment="CELL_CENTER",
            priority_field="NONE",
            cellsize=500
        )

        # Step 7: High pass filter: >= 30 facilities per 1000 people per sq km
        # Then save to file
        filtered_raster = arcpy.sa.Con(arcpy.Raster(output_name) >= 30, arcpy.Raster(output_name))
        filtered_raster.save(output_name + "_filtered")

        # Clean up (replace filtered with just output name)
        arcpy.Delete_management(output_name)
        arcpy.Rename_management(output_name + "_filtered", output_name)
        print(f"Successfully saved bonus question to {output_name}\n")

    def filter_facility_within_radius(self, location: tuple[float, float], radius):
        """
        List all the facilities of the location within the given radius.

        Args:
            location: (x, y) of the current location
            radius: the radius in meters of the circle
        """

        print(f"Here are the facilities within {radius} meters of {location}:")
        northing, easting = location
        for fac in self.fac_list:
            if sqrt((fac.northing - northing) ** 2 + (fac.easting - easting) ** 2) < radius:
                print(f"{fac.dataset} in {fac.fac_name}")
        print()

    def count_facility_by_district(self):
        self.count_facility_by_x("district")

    def count_facility_by_dataset(self):
        self.count_facility_by_x("dataset")

    # helper function
    def count_facility_by_x(self, attr: str):
        """
        Count the facilities grouped by the given attribute.

        Args:
            attr: The attribute name
        """

        print(f"Here are the facilities count by {attr}:")
        # Get a list of tuples[item, occurence]
        counts = list(Counter(getattr(fac, attr) for fac in self.fac_list).items())

        # Sort by occurences in descending order
        counts.sort(key=lambda tup: tup[1], reverse=True)

        for field, count in counts:
            # Convert the integer representation back to a string
            print(f"{field}: {count}")
        print()


class FieldManager:
    def __init__(self, out_feature_name: str):
        self.out_feature_name = out_feature_name

    def add_field(self, field_name: str, field_type: str):
        """
        Add the fields to the feature class. Supports method chaining.
        Args:
            field_name: The new field name to be added
            field_type: The data type of the field (e.g. TEXT, DOUBLE)
        """

        # Add multiple fields and types to the same feature name
        arcpy.AddField_management(self.out_feature_name, field_name, field_type)
        return self  # allows us to chain methods for readability


def main():
    out_feature_name = "sport_facilities"
    polyu_block_z = (818630, 836500)
    ho_man_tin_station = (818940, 836861)
    walkable_distance = 500

    facility_feature = FacilityFeature(WORKSPACE, csv_folder="./csv_data/", feature_name=out_feature_name)
    print("Successfully created geodatabase folder")

    # Compulsory
    facility_feature.point_to_feature_class()
    facility_feature.add_attribute()
    facility_feature.nearest_facility("nearest_facility", polyu_block_z)

    # Bonus
    facility_feature.filter_facility_within_radius(ho_man_tin_station, walkable_distance)
    facility_feature.count_facility_by_dataset()
    facility_feature.count_facility_by_district()
    facility_feature.sport_fac_per_people_per_area()


if __name__ == "__main__":
    main()

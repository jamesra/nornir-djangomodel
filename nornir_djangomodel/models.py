'''
Created on Jun 10, 2014

@author: u0490822
'''
from django.db import models

######################################

class BoundingBox(models.Model):
    minX = models.FloatField()
    minY = models.FloatField()
    minZ = models.FloatField()

    maxX = models.FloatField()
    maxY = models.FloatField()
    maxZ = models.FloatField()

    @property
    def ndims(self):
        ''':return: Number of dimensions.  A null value in minZ or maxZ determines if there are 2 or 3 dimensions to the boundary'''
        if self.minZ is None or self.maxZ is None:
            return 2

        return 3

    def as_tuple(self):
        '''Depending on number of dimensions returns either a bounding box or rectangle
            :return: (minZ, minY, minX, maxZ, maxY, maxX) or (minY, minX, maxY, maxX)
            :rtype: tuple
        '''
        if self.ndims == 2:
            return (self.minY, self.minX, self.maxY, self.maxX)

        return (self.minZ, self.minY, self.minX, self.maxZ, self.maxY, self.maxX)

    def __str__(self):
        if self.minZ is None or self.maxZ is None:
            return "(y:%g, x:%g) (y:%g, z:%g)" % (self.minY,
                                                      self.minX,
                                                      self.maxY,
                                                      self.maxX)
        else:
            return "(z:%g, y:%g, x:%g) (z:%g, y:%g, x:%g)" % (self.minZ,
                                                            self.minY,
                                                            self.minX,
                                                            self.maxZ,
                                                            self.maxY,
                                                            self.maxX)

    # class Meta:
    #    unique_together = (("minX", "minY", "minZ", "maxZ", "maxY", "maxX"),)

class Dataset(models.Model):
    '''A collection of data and coordinate spaces which are part of the same experiment or dataset.'''
    name = models.CharField("Name", max_length=256, primary_key=True)
    path = models.FilePathField("Dataset root", unique=True)

    def __str__(self):
        return self.name


class Channel(models.Model):
    name = models.CharField("Name", max_length=256, primary_key=True)
    dataset = models.ForeignKey("Dataset", related_name="channels", related_query_name="channel")

    def __str__(self):
        return self.name


class Filter(models.Model):
    '''A version of a channel with the same coordinate space, but different intensity mappings for data'''
    name = models.CharField("Name", max_length=256)
    channel = models.ForeignKey("Channel")

    class Meta:
        unique_together = (("name", "channel"),)

    def __str__(self):
        return self.name


class Scale():
    '''Not a django database model.  It is a helper object used for scales'''

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        if not isinstance(val, float):
            raise ValueError("Scale value must be float")

        self._value = val

    @property
    def units(self):
        return self._units

    @units.setter
    def units(self, val):
        if not isinstance(val, str):
            raise ValueError("Scale value must be string")

        self._units = val

    def __init__(self, value, units):
        self.value = value
        self.units = units


class ScaleBase(models.Model):
    '''Abstract class for embedding 2D or 3D scale data in another table'''
    NANOMETER = 'nm'
    MICROMETER = 'um'
    UNITS = ((NANOMETER, 'nm'),
              (MICROMETER, 'um')
              )

    scale_value_X = models.FloatField(null=True)
    scale_units_X = models.CharField(max_length=2, choices=UNITS, default=NANOMETER, null=True)
    scale_value_Y = models.FloatField(null=True)
    scale_units_Y = models.CharField(max_length=2, choices=UNITS, default=NANOMETER, null=True)
    scale_value_Z = models.FloatField(null=True)
    scale_units_Z = models.CharField(max_length=2, choices=UNITS, default=NANOMETER, null=True)

    @property
    def xscale(self):
        if self.scale_value_X is None:
            return None

        return Scale(value=self.scale_value_X, units=self.scale_units_X)

    @xscale.setter
    def xscale(self, val):
        if val is None:
            self.scale_value_X = None
            self.scale_units_X = None
            return

        if not isinstance(val, Scale):
            raise ValueError("Setter for x_scale requires Scale object")

        self.scale_value_X = val.value
        self.scale_units_X = val.units

    @property
    def yscale(self):
        if self.scale_value_Y is None:
            return None

        return Scale(value=self.scale_value_Y, units=self.scale_units_Y)

    @yscale.setter
    def yscale(self, val):
        if val is None:
            self.scale_value_Y = None
            self.scale_units_Y = None
            return

        if not isinstance(val, Scale):
            raise ValueError("Setter for y_scale requires Scale object")

        self.scale_value_Y = val.value
        self.scale_units_Y = val.units

    @property
    def zscale(self):
        if self.scale_value_Z is None:
            return None

        return Scale(value=self.scale_value_Z, units=self.scale_units_Z)

    @zscale.setter
    def zscale(self, val):
        if val is None:
            self.scale_value_Z = None
            self.scale_units_Z = None
            return

        if not isinstance(val, Scale):
            raise ValueError("Setter for z_scale requires Scale object")

        self.scale_value_Z = val.value
        self.scale_units_Z = val.units


    class Meta:
        abstract = True


class CoordSpace(ScaleBase):
    '''A coordinate space'''

    name = models.CharField("Name", max_length=128, primary_key=True)
    dataset = models.ForeignKey("Dataset", related_name="coord_spaces", related_query_name="coord_space")
    bounds = models.ForeignKey(BoundingBox, null=True, help_text="Bounding box of known points in the space")

    @classmethod
    def SectionChannelName(cls, section_number, channel_name, transform_name):
        '''Generate a reasonable name based on a section number, channel name, and transform name'''
        return '%04d.%s.%s' % (section_number, channel_name, transform_name)

    class Meta:
        unique_together = (("dataset", "name"),)

    def __str__(self):
        return self.name

#
# # TODO: Does Tile add any value?  Can it be removed?
# # One argument for keeping it is that it is a good place to store
# # prune scores and histogram data about the tiles.
# class Tile(models.Model):
#
#     number = models.PositiveIntegerField()
#     name = models.CharField(max_length=64)
#     channel = models.ForeignKey(Channel)
#     coord_space = models.ForeignKey(CoordSpace)
#
#     class Meta:
#         unique_together = (("number", "channel", "coord_space"),)
#
#     def __str__(self):
#         return self.name


class Data2D(models.Model):
    '''Data for a coordinate space'''
    name = models.CharField(max_length=64)
    relative_path = models.FilePathField("Image file", primary_key=True)
    image = models.FilePathField()
    level = models.PositiveIntegerField()
    filter = models.ForeignKey(Filter)
    coord_space = models.ForeignKey(CoordSpace)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    # tile = models.ForeignKey(Tile, null=True, blank=True, help_text="If Data represents a tile, this can be set to the tile ID")

    @property
    def channel(self):
        return self.filter.channel

    class Meta:
        unique_together = (("name", "level", "filter", "coord_space"),)

    def __str__(self):
        return self.name


class Mapping2D(models.Model):
    transform_string = models.TextField("Transform string")
    dest_coordinate_space = models.ForeignKey(CoordSpace, related_name="incoming_mappings")
    dest_bounding_box = models.ForeignKey(BoundingBox, related_name="incoming_mappings_bounding_boxes", help_text="Bounding box for this mapping's control points in the destination coordinate space")
    src_coordinate_space = models.ForeignKey(CoordSpace, related_name="outgoing_mappings")
    src_bounding_box = models.ForeignKey(BoundingBox, related_name="outgoing_mappings_bounding_boxes", help_text="Bounding box for this mapping's control points in the source coordinate space")

    @property
    def Z(self):
        return self.dest_bounding_box.minZ

    def __str__(self):
        return self.src_coordinate_space.name + " -> " + self.dest_coordinate_space.name

#
# class Mapping2D(Mapping2DBase):
#
#
#     @property
#     def Z(self):
#         return self.dest_bounding_box.minZ
#
#     class Meta:
#         abstract = True
#
#
# class Tile2DMapping(Mapping2DBase):
#     '''Maps tile into a 2D space'''
#     tile = models.ForeignKey(Tile)
#
#     def __str__(self):
#         return self.tile.name + ' -> ' + self.dest_coordinate_space.name


#===============================================================================
#
#
# class Space3D(models.Model):
#     VOLUME = 'V'
#     SLICE_TO_SLICE = 'S'
#     TILE_MAPPING = 'TM'
#     DATA_FORMAT = {VOLUME, 'Volume',
#                    SLICE_TO_SLICE, 'Slice to slice',
#                    TILE_MAPPING, 'Tile to volume mappings'}
#
#     class Meta:
#         abstract = True
#
#
# class Space2D(models.Model):
#     '''Abstract class for 2D data'''
#     IMAGE = 'I'
#     MOSAIC = 'M'
#     DATA_FORMAT = {IMAGE, 'Image',
#                  MOSAIC, 'Mosaic'}
#
#     class Meta:
#         abstract = True
#
#
# class Mosaic(Space2D):
#     format = Space2D.MOSAIC
#     name = models.CharField("Name", max_length=256)
#     channel = models.ForeignKey(Channel)
#
#
# class Mapping2D(models.Model):
#     # Transform_string to warp image to destination.  If None the identity transform is used
#     transform_string = models.TextField()
#     mosaic = models.ForeignKey(Mosaic)
#     source_space = models.ForeignKey(Data2D)
#     target_space = models.ForeignKey(Data2D)
#
#
# class Bounds(models.Model):
#     minX = models.FloatField()
#     minY = models.FloatField()
#     minZ = models.FloatField()
#
#     maxX = models.FloatField()
#     maxY = models.FloatField()
#     maxZ = models.FloatField()
#
#
# class Dataset(models.Model):
#     path = models.FilePathField("Full path to volume root")
#     name = models.CharField("Name", max_length=256)
#     dimensions = models.PositiveIntegerField("Number of dimensions")
#     bounds = models.ForeignKey(Bounds)
#
#
# class Volume(models.Model):
#     '''3D data'''
#     name = models.CharField("Name", max_length=256)
#     path = models.FilePathField("Full path to volume root")
#     dimensions = models.PositiveIntegerField("Number of dimensions")
#
#
#
# class Mosaic(models.Model):
#     name = models.CharField("Name", max_length=256)
#     path = models.FilePathField("Mosaic Path")
#     channel = models.CharField("Channel", max_length=256)
#     target_space = models.CharField("Target Space", max_length=256)
#===============================================================================
'''
Created on Jun 11, 2014

@author: u0490822
'''
import os
import nornir_volumemodel
import nornir_imageregistration
import nornir_imageregistration.files
import nornir_imageregistration.transforms
from nornir_imageregistration.spatial import *
import glob
from . import models


def GetOrCreateDataset(Name, Path):

        (db_vol, created) = models.Dataset.objects.get_or_create(name=Name, path=Path)
        if created:
            db_vol.save()

        return db_vol


def CreateBoundingRect(rect_bounds, minZ, maxZ=None):
    '''
    :param rect bounds: (minY minX MaxY maxX)
    :param float minZ: Z level of bounding rect
    :param float maxZ: Equal to minZ if unspecified
    '''

    if maxZ is None:
        maxZ = minZ

    db_boundingbox = models.BoundingBox.objects.create(minX=rect_bounds[iRect.MinX],
                                                       minY=rect_bounds[iRect.MinY],
                                                       minZ=minZ,
                                                       maxX=rect_bounds[iRect.MaxX],
                                                       maxY=rect_bounds[iRect.MaxY],
                                                       maxZ=maxZ)
    db_boundingbox.save()
    return db_boundingbox


def CreateBoundingBox(bounds):
    '''
    :param rect bounds: (minZ minY minX MaxZ MaxY maxX)
    '''
    db_boundingbox = models.BoundingBox.objects.create(minX=bounds[iBox.MinX],
                                                       minY=bounds[iBox.MinY],
                                                       minZ=bounds[iBox.MinZ],
                                                       maxX=bounds[iBox.MaxX],
                                                       maxY=bounds[iBox.MaxY],
                                                       maxZ=bounds[iBox.MaxZ])
    db_boundingbox.save()
    return db_boundingbox


def GetCoordSpace(channel, name):
    section = channel.Parent
    coord_space_name = models.CoordSpace.SectionChannelName(section.Number, channel.Name, name)
    return models.CoordSpace.objects.get(name=coord_space_name)


def ConvertToDBBounds(bounds, ZLevel=None):
    '''Convert the passed object to a database bounds object, create a new row if needed'''
    db_bounds = None
    if not bounds is None:
        if isinstance(bounds, models.BoundingBox):
            db_bounds = bounds
        elif isinstance(bounds, Rectangle):
            if ZLevel is None:
                raise ValueError("ZLevel must be specified if a rectangle is passed")
            db_bounds = CreateBoundingRect(bounds.ToArray(), ZLevel)
        else:  # isinstance(bounds, tuple) or isinstance(bounds, list) or isinstance(bounds):
            if len(bounds) == 4:
                if ZLevel is None:
                    raise ValueError("ZLevel must be specified if a rectangle is passed")
                db_bounds = CreateBoundingRect(bounds, ZLevel)
            elif len(bounds) == 6:
                db_bounds = CreateBoundingBox(bounds)

        if db_bounds is None:
            raise TypeError("Unexpected type for bounds argument: " + str(bounds))

    return db_bounds


def GetOrCreateCoordSpace(db_dataset_name, coord_space_name, bounds):
    '''
    :param Channel channel: The nornir channel which our space originates from
    :param name name: The name of the space, usually derived from the transform
    :param Rectangle bounds: Bounding box for coord space 
    :return: section#.channel.name
    '''



    db_bounds = ConvertToDBBounds(bounds)
    db_dataset = models.Dataset.objects.get(name=db_dataset_name)

    (db_coordspace, created) = models.CoordSpace.objects.get_or_create(name=coord_space_name,
                                                                       dataset=db_dataset)

    need_save = created
    if db_coordspace.bounds is None and not db_bounds is None:
        db_coordspace.bounds = db_bounds
        need_save = True

    if need_save:
        db_coordspace.save()
        print("Created coord space: %s" % (coord_space_name))

    return db_coordspace


def _iterate_volume_channels(volumexml_model):
    '''Yield a tuple of (filter, parent_dict) for each channel in the volume'''
    for block in volumexml_model.Blocks:
        for section in block.Sections:
            for channel in section.Channels:
                yield (channel, {'volume': volumexml_model,
                       'block': block,
                       'section': section,
                       'channel': channel})


def _iterate_volume_filters(volumexml_model):
    '''Yield a tuple of (filter, parent_dict) for each filter in the volume'''
    for (channel, parent_dict) in _iterate_volume_channels(volumexml_model):
        for filter_obj in channel.Filters.values():
            parent_dict['filter'] = filter_obj
            yield (filter_obj, parent_dict)


class VolumeXMLImporter():

    @property
    def volumexml_model(self):
        '''The volume model this object was created to import'''
        return self._volumexml_model

    @property
    def dataset_name(self):
        '''The dataset name this importer is importing to'''
        return self._dataset_name

    @property
    def db_dataset(self):
        return models.Dataset.objects.get(name=self.dataset_name)

    def __init__(self, volumexml_model):
        self._volumexml_model = volumexml_model
        self._dataset_name = volumexml_model.Name

    @classmethod
    def Import(cls, vol_model, dataset_name=None):
        '''Given a nornir volume model populate the django model.
        :return volume volume: Volume model'''
        if(isinstance(vol_model, str)):
            vol_model = nornir_volumemodel.Load_Xml(vol_model)

        importer_obj = VolumeXMLImporter(vol_model)

        if dataset_name is None:
            dataset_name = vol_model.Name

        GetOrCreateDataset(dataset_name, Path=vol_model.Path)

        importer_obj.AddChannelsAndFilters()
        importer_obj.AddTiles()
        importer_obj.AddChannelTransforms()

        return dataset_name

    def AddChannelsAndFilters(self):
        db_dataset = self.db_dataset

        for (filter_obj, parent_dict) in _iterate_volume_filters(self.volumexml_model):
            channel_obj = parent_dict['channel']
            (db_channel, created) = models.Channel.objects.get_or_create(name=channel_obj.Name, dataset=db_dataset)
            if created:
                db_channel.save()

            (db_filter, created) = models.Filter.objects.get_or_create(name=filter_obj.Name, channel=db_channel)
            if created:
                db_filter.save()

        return

    def AddTiles(self):
        for (filter_obj, parent_dict) in _iterate_volume_filters(self.volumexml_model):
            channel_obj = parent_dict['channel']
            ZLevel = parent_dict['section'].Number
            self.AddTilePyramid(channel_obj, filter_obj.Name, ZLevel, filter_obj.TilePyramid)

    def AddChannelTransforms(self):
        for (channel_obj, parent_dict) in _iterate_volume_channels(self.volumexml_model):
            for transform_obj in channel_obj.Transforms.values():
                (base, ext) = os.path.splitext(transform_obj.Path)
                if ext == '.mosaic':
                    ZLevel = parent_dict['section'].Number
                    self.AddChannelMosaic(channel_obj, transform_obj, ZLevel)

    def GetOrCreateTileCoordSpace(self, channel, name, bounds, scale=None):

        section = channel.Parent
        coord_space_name = models.CoordSpace.SectionChannelName(section.Number, channel.Name, name)

        db_coordspace = GetOrCreateCoordSpace(self.dataset_name, coord_space_name, bounds)

        if db_coordspace.xscale is None or db_coordspace.xscale.value != channel.Scale.X.UnitsPerPixel or db_coordspace.yscale.value != channel.Scale.Y.UnitsPerPixel:
            db_coordspace.xscale = models.Scale(value=channel.Scale.X.UnitsPerPixel, units=channel.Scale.X.UnitsOfMeasure)
            db_coordspace.yscale = models.Scale(value=channel.Scale.Y.UnitsPerPixel, units=channel.Scale.Y.UnitsOfMeasure)
            db_coordspace.zscale = None

            db_coordspace.save()

        return db_coordspace

    def AddChannelMosaic(self, channel, transform_obj, ZLevel):

        (db_channel, created) = models.Channel.objects.get_or_create(name=channel.Name)

        mosaicfile = nornir_imageregistration.files.MosaicFile.Load(transform_obj.FullPath)
        if mosaicfile is None:
            return

        mosaic = nornir_imageregistration.mosaic.Mosaic(mosaicfile.ImageToTransformString)

        db_bounds = CreateBoundingRect(mosaic.FixedBoundingBox, minZ=ZLevel)
        db_mosaic_coordspace = GetOrCreateCoordSpace(self.dataset_name, transform_obj.Name, bounds=db_bounds)

        for (name, transform) in mosaic.ImageToTransform.items():

            (tile_number, ext) = os.path.splitext(name)
            tile_number = int(tile_number)

            db_bounds = ConvertToDBBounds(transform.MappedBoundingBox, ZLevel=ZLevel)

            db_tile_coordspace = self.GetOrCreateTileCoordSpace(channel, 'Tile%d' % tile_number, db_bounds, ZLevel)

    #         (db_tile, created) = models.Tile.objects.get_or_create(number=int(tile_number),
    #                                                                name=name,
    #                                                                channel=db_channel,
    #                                                                coord_space=db_tile_coordspace)
    #         if created:
    #             db_tile.save()

            # transform_string = nornir_imageregistration.transforms.factory.TransformToIRToolsString(transform)
            transform_string = mosaicfile.ImageToTransformString[name]
            db_dest_bounding_box = CreateBoundingRect(transform.FixedBoundingBox, ZLevel)

            (db_mapping, created) = models.Mapping2D.objects.get_or_create(
                                                             src_coordinate_space=db_tile_coordspace,
                                                             src_bounding_box=db_tile_coordspace.bounds,
                                                             transform_string=transform_string,
                                                             dest_coordinate_space=db_mosaic_coordspace,
                                                             dest_bounding_box=db_dest_bounding_box)
            if created:
                db_mapping.save()

    def AddTilePyramid(self, channel, filter_name, ZLevel, tile_pyramid):

        if tile_pyramid is None:
            return

        (db_channel, created) = models.Channel.objects.get_or_create(name=channel.Name)
        (db_filter, created) = models.Filter.objects.get_or_create(name=filter_name, channel=db_channel)

        for level in tile_pyramid.Levels:
            level_number = level.Number

            self.BulkAddData2D(channel,
                          level.FullPath,
                          level.RelativePath,
                          tile_pyramid.ImageFormatExt,
                          db_channel,
                          db_filter,
                          ZLevel,
                          level_number)

    def BulkAddData2D(self, channel, full_path, rel_path, extension, db_channel, db_filter, ZLevel, level_number):
        image_paths = glob.glob(os.path.join(full_path, '*' + extension))

        for image_path in image_paths:
            if os.path.exists(image_path):
                img_name = os.path.basename(image_path)
                (img_number, ext) = os.path.splitext(img_name)

                (height, width) = nornir_imageregistration.GetImageSize(image_path)
                db_bounds = CreateBoundingRect(Rectangle.CreateFromPointAndArea((0, 0), (height, width)), minZ=ZLevel)
                db_tile_coordspace = self.GetOrCreateTileCoordSpace(channel, 'Tile%d' % int(img_number), bounds=db_bounds)
                # db_tile_mapping = GetTileMapping(tile_number=img_number, Z=ZLevel, )

                img_rel_path = os.path.join(rel_path, img_name)

                (db_data, created) = models.Data2D.objects.get_or_create(name=img_name,
                                                                         image=os.path.abspath(image_path),
                                                                         filter=db_filter,
                                                                         level=level_number,
                                                                         relative_path=img_rel_path,
                                                                         coord_space=db_tile_coordspace,
                                                                         width=width,
                                                                         height=height)
                if created:
                    db_data.save()


if __name__ == '__main__':
    pass
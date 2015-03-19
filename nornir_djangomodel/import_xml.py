'''
Created on Jun 11, 2014

@author: u0490822
'''
import os
import copy
import nornir_volumemodel
import nornir_imageregistration
import nornir_imageregistration.files
import nornir_imageregistration.transforms
from nornir_imageregistration.spatial import *
import glob
from . import models
import pickle

import nornir_djangomodel.settings as settings


class QuickPickleHelper():
    cachepath = os.curdir

    @classmethod
    def SaveVariable(cls, var, filename):
        fullpath = os.path.join(QuickPickleHelper.cachepath, filename)

        if not os.path.exists(os.path.dirname(fullpath)):
            os.makedirs(os.path.dirname(fullpath))

        with open(fullpath, 'wb') as filehandle:
            print("Saving: " + fullpath)
            pickle.dump(var, filehandle)

    @classmethod
    def ReadOrCreateVariable(cls, varname, createfunc=None, **kwargs):
        '''Reads variable from disk, call createfunc if it does not exist'''

        var = None
        if hasattr(cls, varname):
            var = getattr(cls, varname)

        if var is None:
            path = os.path.join(QuickPickleHelper.cachepath, varname + ".pickle")
            if os.path.exists(path):
                with open(path, 'rb') as filehandle:
                    try:
                        var = pickle.load(filehandle)
                        print("Loaded %s variable from pickle file: " % (varname))
                    except:
                        var = None
                        print("Unable to load %s variable from pickle file: %s" % (varname, path))

            if var is None and not createfunc is None:
                var = createfunc(**kwargs)
                cls.SaveVariable(var, path)
                setattr(cls, varname, var)
                print("Created %s variable from create function" % (varname))
        else:
            print("Found %s variable already in memory" % (varname))

        return var


def GetOrCreateDataset(Name, Path):

        (db_vol, created) = models.Dataset.objects.get_or_create(name=Name, path=Path)
        if created:
            db_vol.save()

        return db_vol


def CreateBoundingRect(rect_bounds, minZ, maxZ=None, Save=True):
    '''
    :param rect bounds: (minY minX MaxY maxX)
    :param float minZ: Z level of bounding rect
    :param float maxZ: Equal to minZ if unspecified
    '''

    if maxZ is None:
        maxZ = minZ

    db_boundingbox = models.BoundingBox(minX=rect_bounds[iRect.MinX],
                                                       minY=rect_bounds[iRect.MinY],
                                                       minZ=minZ,
                                                       maxX=rect_bounds[iRect.MaxX],
                                                       maxY=rect_bounds[iRect.MaxY],
                                                       maxZ=maxZ)
    if Save:
        db_boundingbox.save()

    return db_boundingbox



def GetOrCreateBoundingRect(rect_bounds, minZ, maxZ=None, Save=True):
    '''
    :param rect bounds: (minZ minY minX MaxZ MaxY maxX)
    '''

    if maxZ is None:
        maxZ = minZ

    (db_boundingbox, created) = models.BoundingBox.objects.get_or_create(minX=rect_bounds[iRect.MinX],
                                                                           minY=rect_bounds[iRect.MinY],
                                                                           minZ=minZ,
                                                                           maxX=rect_bounds[iRect.MaxX],
                                                                           maxY=rect_bounds[iRect.MaxY],
                                                                           maxZ=maxZ)

    if created and Save:
        db_boundingbox.save()

    return db_boundingbox


def CreateBoundingBox(bounds, Save=True):
    '''
    :param rect bounds: (minZ minY minX MaxZ MaxY maxX)
    '''
    db_boundingbox = models.BoundingBox(minX=bounds[iBox.MinX],
                                                       minY=bounds[iBox.MinY],
                                                       minZ=bounds[iBox.MinZ],
                                                       maxX=bounds[iBox.MaxX],
                                                       maxY=bounds[iBox.MaxY],
                                                       maxZ=bounds[iBox.MaxZ])

    if Save:
        db_boundingbox.save()

    return db_boundingbox

def GetOrCreateBoundingBox(bounds):
    '''
    :param rect bounds: (minZ minY minX MaxZ MaxY maxX)
    '''
    (db_boundingbox, created) = models.BoundingBox.objects.get_or_create(minX=bounds[iBox.MinX],
                                                              minY=bounds[iBox.MinY],
                                                              minZ=bounds[iBox.MinZ],
                                                              maxX=bounds[iBox.MaxX],
                                                              maxY=bounds[iBox.MaxY],
                                                              maxZ=bounds[iBox.MaxZ])

    if created:
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


def GetOrCreateCoordSpace(db_dataset, coord_space_name, bounds, ForceSaveOnCreate=False):
    '''
    :param Channel channel: The nornir channel which our space originates from
    :param name name: The name of the space, usually derived from the transform
    :param Rectangle bounds: Bounding box for coord space 
    :return: section#.channel.name
    '''

    db_bounds = ConvertToDBBounds(bounds) 

    (db_coordspace, created) = models.CoordSpace.objects.get_or_create(name=coord_space_name, dataset=db_dataset)

    need_save = created
    if not db_bounds is None:
        # Trying to avoid looking up the relation unless necessary
        if created:
            db_coordspace.bounds = db_bounds
            need_save = True

    if ForceSaveOnCreate:
        if need_save:
            db_coordspace.save()

        return db_coordspace

    return (db_coordspace, created)


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
        if self._db_dataset is None:
            self._db_dataset = models.Dataset.objects.get(name=self.dataset_name)

        return self._db_dataset

    def __init__(self, volumexml_model):
        self._volumexml_model = volumexml_model
        self._dataset_name = volumexml_model.Name
        self._db_dataset = None

    @classmethod
    def _LoadVolumeFromCacheIfPossible(cls, vol_model):
        assert(isinstance(vol_model, str))
        import_dirname = os.path.dirname(vol_model)
        QuickPickleHelper.cachepath = import_dirname
        vol_model = QuickPickleHelper.ReadOrCreateVariable(varname='vol_model', createfunc=nornir_volumemodel.Load_Xml, VolumePath=vol_model)
        return vol_model

    @classmethod
    def Import(cls, vol_model, dataset_name=None, section_list=None):
        '''Given a nornir volume model populate the django model.
        :return volume volume: Volume model'''

        if isinstance(vol_model, str):
            path_str = vol_model
            
            if settings.NORNIR_DJANGOMODEL_USEVOLUMEXMLCACHE:
                vol_model = VolumeXMLImporter._LoadVolumeFromCacheIfPossible(vol_model)
            else:
                vol_model = nornir_volumemodel.Load_Xml(vol_model)
                
            vol_model.Path = os.path.dirname(path_str)

        importer_obj = VolumeXMLImporter(vol_model)

        if dataset_name is None:
            dataset_name = vol_model.Name

        GetOrCreateDataset(dataset_name, Path=vol_model.Path)

        importer_obj.AddChannelsAndFilters()
        importer_obj.AddTiles(section_list)
        importer_obj.AddChannelDetails(section_list)

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

    def AddTiles(self, section_list=None):
        for (filter_obj, parent_dict) in _iterate_volume_filters(self.volumexml_model):
            channel_obj = parent_dict['channel']
            ZLevel = parent_dict['section'].Number
            if section_list is None or ZLevel in section_list:
                self.AddTilePyramid(channel_obj, filter_obj.Name, ZLevel, filter_obj.TilePyramid)

    def AddChannelDetails(self, section_list=None):
        for (channel_obj, parent_dict) in _iterate_volume_channels(self.volumexml_model):
            ZLevel = parent_dict['section'].Number
            if section_list is None or ZLevel in section_list:    
                for transform_obj in channel_obj.Transforms.values():
                    (base, ext) = os.path.splitext(transform_obj.Path)
                    if ext == '.mosaic': 
                        self.AddChannelMosaic(channel_obj, transform_obj, ZLevel)
            
        #Transforms sometimes live in different sections than the filters they create, such as Registered_* filters.  Run this as a second loop to 
        #ensure all the coord_space rows have been created 
        #=======================================================================
        # for (channel_obj, parent_dict) in _iterate_volume_channels(self.volumexml_model):
        #     ZLevel = parent_dict['section'].Number
        #     if section_list is None or ZLevel in section_list:           
        #         for filter_obj in channel_obj.Filters.values():
        #             if filter_obj.ImageSet is None:
        #                 continue 
        #             
        #             self.AddOrUpdateFilterImageSet(channel_obj, filter_obj, filter_obj.ImageSet, ZLevel) 
        #=======================================================================
               
         
    def GetOrCreateTileCoordSpace(self, channel, name, bounds, scale=None):

        section = channel.Parent
        coord_space_name = models.CoordSpace.SectionChannelName(section.Number, channel.Name, name)
        needsave = False 
        
        (db_coordspace, created) = GetOrCreateCoordSpace(self.db_dataset, coord_space_name, bounds)

        if db_coordspace.xscale is None or db_coordspace.xscale.value != channel.Scale.X.UnitsPerPixel or db_coordspace.yscale.value != channel.Scale.Y.UnitsPerPixel:
            db_coordspace.xscale = models.Scale(value=channel.Scale.X.UnitsPerPixel, units=channel.Scale.X.UnitsOfMeasure)
            db_coordspace.yscale = models.Scale(value=channel.Scale.Y.UnitsPerPixel, units=channel.Scale.Y.UnitsOfMeasure)
            db_coordspace.zscale = None

            needsave = True

        if needsave or created:
            db_coordspace.save()

        return (db_coordspace, created)

    @classmethod
    def BatchCreateDestinationBoundingRects(cls, ImageToTransform, ZLevel):
        ImageToBounds = {}
        dbBounds_list = []

        for (name, transform) in ImageToTransform.items():
            db_dest_bounding_box = CreateBoundingRect(transform.FixedBoundingBox, ZLevel, Save=False)
            dbBounds_list.append(db_dest_bounding_box)
            ImageToBounds[name] = db_dest_bounding_box

        # This doesn't update the ids of the DB bounds, so they can't be used for other purposes
        models.BoundingBox.objects.bulk_create(dbBounds_list)
        return ImageToBounds
    
    
    def AddOrUpdateFilterImageSet(self, channel_obj, filter_obj, imageset_obj, ZLevel):
        
        transform_name = imageset_obj.InputTransform
        db_coord_space = GetCoordSpace(channel_obj, transform_name)
        
        (db_channel, created) = models.Channel.objects.get_or_create(name=channel_obj.Name)
        if created:
            db_channel.save()
        
        (db_filter, created) = models.Filter.objects.get_or_create(name=filter_obj.Name, channel=db_channel)
        if created:
            db_filter.save()
        
        for (level_number, image) in imageset_obj.GetImages():
            img_name = os.path.basename(image.fullpath) 
            (height, width) = nornir_imageregistration.GetImageSize(image.fullpath)
            db_data = models.Data2D(name=img_name,
                                     image=os.path.abspath(image.fullpath),
                                     filter=db_filter,
                                     level=level_number,
                                     relative_path=image.fullpath,
                                     coord_space=db_coord_space,
                                     width=width,
                                     height=height)
            
        
    def AddChannelMosaic(self, channel, transform_obj, ZLevel):
        '''Add all of the tiles associated with the transforms in a mosaic file'''
        
        (db_channel, created) = models.Channel.objects.get_or_create(name=channel.Name)
        if created:
            db_channel.save()

        mosaicfile = nornir_imageregistration.files.MosaicFile.Load(transform_obj.FullPath)
        if mosaicfile is None:
            return

        mosaic = nornir_imageregistration.mosaic.Mosaic(copy.copy(mosaicfile.ImageToTransformString))
        db_bounds = CreateBoundingRect(mosaic.FixedBoundingBox, minZ=ZLevel)
        db_mosaic_coordspace = GetOrCreateCoordSpace(self.db_dataset, transform_obj.Name, bounds=db_bounds, ForceSaveOnCreate=True)

        db_mapping_list = []

        print("Importing mappings from %s into %s" % (transform_obj.FullPath, db_mosaic_coordspace.name))

        # Batch create destination bounding rectangles for each transform

        # ImageToDestinationBounds = VolumeXMLImporter.BatchCreateDestinationBoundingRects(mosaic.ImageToTransform, ZLevel)

        db_src_tile_bounds = None

        for (name, transform) in mosaic.ImageToTransform.items():

            (tile_number, ext) = os.path.splitext(name)
            tile_number = int(tile_number)

            if db_src_tile_bounds is None:
                db_src_tile_bounds = CreateBoundingRect(transform.MappedBoundingBox, minZ=ZLevel)

            (db_tile_coordspace, created_tile_coordspace) = self.GetOrCreateTileCoordSpace(channel, 'Tile%d' % tile_number, db_src_tile_bounds, ZLevel)

    #         (db_tile, created) = models.Tile.objects.get_or_create(number=int(tile_number),
    #                                                                name=name,
    #                                                                channel=db_channel,
    #                                                                coord_space=db_tile_coordspace)
    #         if created:
    #             db_tile.save()

            # transform_string = nornir_imageregistration.transforms.factory.TransformToIRToolsString(transform)
            transform_string = mosaicfile.ImageToTransformString[name]
            # db_dest_bounding_box = ImageToDestinationBounds[name]
            db_dest_bounding_box = CreateBoundingRect(transform.FixedBoundingBox, ZLevel)
            assert(db_dest_bounding_box is not None)
            
            existing_db_mapping = models.Mapping2D.objects.filter(src_coordinate_space=db_tile_coordspace,
                                                                  dest_coordinate_space=db_mosaic_coordspace) 
            if existing_db_mapping.exists():
                db_mapping = existing_db_mapping.first()
                db_mapping.transform_string = transform_string
                db_mapping.src_bounding_box = db_src_tile_bounds
                db_mapping.dest_bounding_box = db_dest_bounding_box
                
                db_mapping.save()

            else:
                db_mapping = models.Mapping2D(src_coordinate_space=db_tile_coordspace,
                                                     src_bounding_box=db_src_tile_bounds,
                                                     transform_string=transform_string,
                                                     dest_coordinate_space=db_mosaic_coordspace,
                                                     dest_bounding_box=db_dest_bounding_box)

                db_mapping_list.append(db_mapping)
            
            db_mosaic_coordspace.UpdateBounds(db_dest_bounding_box)

        models.Mapping2D.objects.bulk_create(db_mapping_list)
        
        #Save the updated coordspace bounding box
        db_mosaic_coordspace.bounds.save()
        
        
    

    def AddTilePyramid(self, channel, filter_name, ZLevel, tile_pyramid):

        if tile_pyramid is None:
            return

        (db_channel, created) = models.Channel.objects.get_or_create(name=channel.Name)
        if created:
            db_channel.save()

        (db_filter, created) = models.Filter.objects.get_or_create(name=filter_name, channel=db_channel)
        if created:
            db_filter.save()

        for level in tile_pyramid.Levels:
            level_number = level.Number

            print("Adding %d.%s.%s.%d" % (ZLevel, channel.Name, filter_name, level.Number))

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

        if len(image_paths) == 0:
            return

        (height, width) = nornir_imageregistration.GetImageSize(image_paths[0])
        db_bounds = CreateBoundingBox((ZLevel, 0, 0, ZLevel, height, width))

        db_data_list = []
        img_rel_path_table = {}

        for image_path in image_paths:
            # if os.path.exists(image_path):
            img_name = os.path.basename(image_path)
            (img_number, ext) = os.path.splitext(img_name)

            # (height, width) = nornir_imageregistration.GetImageSize(image_path)
            # db_bounds = CreateBoundingRect(Rectangle.CreateFromPointAndArea((0, 0), (height, width)), minZ=ZLevel)
            (db_tile_coordspace, created_tile_coordspace) = self.GetOrCreateTileCoordSpace(channel, 'Tile%d' % int(img_number), bounds=db_bounds)

            # db_tile_mapping = GetTileMapping(tile_number=img_number, Z=ZLevel, )

            img_rel_path = os.path.join(rel_path, img_name)

            if img_rel_path in img_rel_path_table:
                print("Trying to create this tile twice: %s" % (img_rel_path))
                continue

            img_rel_path_table[img_rel_path] = True
            
            existing_db_data = models.Data2D.objects.filter(relative_path=img_rel_path) 
            if existing_db_data.exists():
                #Update path
                db_data = existing_db_data.first()
                db_data.image = os.path.abspath(image_path)
                db_data.filter = db_filter
                db_data.level = level_number
                db_data.coord_space = db_tile_coordspace
                db_data.width = width
                db_data.height = height
                
                db_data.save()
                
            else:
                #Create new, bulk update path
                db_data = models.Data2D(name=img_name,
                             image=os.path.abspath(image_path),
                             filter=db_filter,
                             level=level_number,
                             relative_path=img_rel_path,
                             coord_space=db_tile_coordspace,
                             width=width,
                             height=height)

                db_data_list.append(db_data)

        if len(db_data_list) > 0:
            models.Data2D.objects.bulk_create(db_data_list)

#        db_data.save()


if __name__ == '__main__':
    pass
 # -*- coding: utf-8 -*-

# ╦╔╦╗╔═╗╔═╗╦═╗╔╦╗╔═╗
# ║║║║╠═╝║ ║╠╦╝ ║ ╚═╗
# ╩╩ ╩╩  ╚═╝╩╚═ ╩ ╚═╝
#==================================================
#.NET Imports
import clr
clr.AddReference('System')
clr.AddReference("System.Core")

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *
from Autodesk.Revit.DB.Architecture import RoomTag
from System.Collections.Generic import List
from pyrevit import forms

# ╦  ╦╔═╗╦═╗╦╔═╗╔╗ ╦  ╔═╗╔═╗
# ╚╗╔╝╠═╣╠╦╝║╠═╣╠╩╗║  ║╣ ╚═╗
#  ╚╝ ╩ ╩╩╚═╩╩ ╩╚═╝╩═╝╚═╝╚═╝
#==================================================
app    = __revit__.Application
uidoc  = __revit__.ActiveUIDocument
doc    = __revit__.ActiveUIDocument.Document #type:Document


# ╔╦╗╔═╗╦╔╗╔
# ║║║╠═╣║║║║
# ╩ ╩╩ ╩╩╝╚╝
#==================================================
#LIST SPATIAL TAGS
#==================================================
#all tags for rooms, areas
all_spatial_tags = (
    FilteredElementCollector(doc)
    .OfClass(SpatialElementTag)
    .WhereElementIsNotElementType()
    .ToElements()
)

#orphaned tags
orphaned_spatial_tags = []

for tag in all_spatial_tags:

    #filter room tags
    if not isinstance(tag, RoomTag):
        continue

    #filter orphaned tags
    if not tag.IsOrphaned:
        continue

    #get tag view
    view = doc.GetElement(tag.OwnerViewId)
    if view is None:
        continue

    #get tag level
    tag_level = view.GenLevel
    if tag_level is None:
        print("Tag {} has no associated level".format(tag.Id.Value))
        continue

    orphaned_spatial_tags.append((tag, view, tag_level))

print("Total Spatial Tags:", len(all_spatial_tags))
print("Orphaned Spatial Tags:", len(orphaned_spatial_tags))
print("==================================================")

#==================================================
#LEVELS
#==================================================

all_levels = (FilteredElementCollector(doc).OfClass(Level).ToElements())
level_names = [level.Name for level in all_levels]

#==================================================
#COLLECT REVIT LINKS
#==================================================

linked_rooms =[]

#all links
links = (
    FilteredElementCollector(doc).
    OfClass(RevitLinkInstance).
    ToElements()
)
for link in links:
    link_doc = link.GetLinkDocument()

    if link_doc is None:
        continue

    level_link = None
    for level in all_levels:
        if level.Name in link.Name:
            level_link = level
            break

    # Skip links without matching level
    if level_link is None:
        print("No level found for link: {}".format(link.Name))
        print("==================================================")
        continue

    #get rooms in links         
    rooms =(
        FilteredElementCollector(link_doc)
        .OfCategory(BuiltInCategory.OST_Rooms)
        .WhereElementIsNotElementType()
        .ToElements()
    )

    for room in rooms:
        linked_rooms.append((link, level_link, room))

#==================================================
# MATCH TAGS AND LINKS BY LEVEL
#==================================================
for tag, view, tag_level in orphaned_spatial_tags:
    temp_rooms = []
    matching_rooms = []
    matching_rooms_names = []

    selected_tag = tag

    #filter rooms by level
    for link, level_link, room in linked_rooms:   
        if tag_level.Name == level_link.Name:
            temp_rooms.append((link,room,level_link))

#==================================================
# MATCH TAGS AND ROOMS BY POSITION
#==================================================

    #Get tag position
    tag_position = selected_tag.TagHeadPosition

    #Get room bounding box
    for link, room, level_link in temp_rooms:

        bbox = room.get_BoundingBox(None)
        if bbox is None:
            continue

        #Compare tag position with room bounding box
        X_match = bbox.Min.X <= tag_position.X <= bbox.Max.X 
        Y_match = bbox.Min.Y <= tag_position.Y <= bbox.Max.Y

        if X_match and Y_match:
            matching_rooms.append((link, room,level_link))

            room_name = room.get_Parameter(BuiltInParameter.ROOM_NAME).AsString()
            matching_rooms_names.append(room_name)
        
            print("MATCH FOUND")
            print("Tag ID: {}".format(selected_tag.Id.Value))
            print("Room: {}".format(room_name))
            print("Room ID: {}".format(room.Id.Value))
            print("Link ID: {}".format(link.Id.Value))
            print("Level: {}".format(level_link.Name))
            print("==================================================")

#==================================================
# ROOM SELECTION (IF APPLIES)
#==================================================

    selected_room = None
    if len(matching_rooms) == 1:
        selected_room = matching_rooms[0]

    elif len(matching_rooms) > 1:
        room_options ={}

        #open tag view
        if uidoc.ActiveView.Id != view.Id:
                uidoc.ActiveView = view

        #select tag
        seleted_ids = List[ElementId]()
        seleted_ids.Add(selected_tag.Id)
        uidoc.Selection.SetElementIds(seleted_ids)

        #zoom
        points_x = [tag_position.X]
        points_y = [tag_position.Y]

        padding = 10.0
        min_x = min(points_x) - padding
        max_x = max(points_x) + padding
        min_y = min(points_y) - padding
        max_y = max(points_y) + padding

        corner1 = XYZ(min_x, min_y, 0)
        corner2 = XYZ(max_x, max_y, 0)

        #find the open UIView
        for ui_view in uidoc.GetOpenUIViews():
            if ui_view.ViewId == view.Id:
                ui_view.ZoomAndCenterRectangle(corner1, corner2)
                break



        #select room from list
        for link, room, level_link in matching_rooms:
            room_name = room.get_Parameter(BuiltInParameter.ROOM_NAME).AsString()

            label = "{} | Room Id: {} | Link Id: {} | Level: {}".format(
                room_name,
                room.Id.Value,
                link.Id.Value,
                level_link.Name
            )

            room_options[label] = (link, room, level_link)

        selection = forms.SelectFromList.show(
            sorted(room_options.keys()),
            title="Select a room to reconcile the tag with",
            button_name="Select Room",
            multiselect=False
        )

        if selection is not None:
            selected_room = room_options[selection]

#==================================================
# RESULTS AND NEW TAG INFORMATION
#==================================================

    if selected_room is not None:

        selected_link, selected_room_element, level_link = selected_room

        print("Selected Rooms: 1")
        print("Room ID: {}".format(selected_room_element.Id.Value))
        print("Link ID: {}".format(selected_link.Id.Value))
        print("Level: {}".format(level_link.Name))


#==================================================
# TEST LINK COORDINATES
#==================================================

        room = selected_room_element
        link = selected_link

        transform = link.GetTotalTransform()
        inverse = transform.Inverse

        tag_position = selected_tag.TagHeadPosition
        point_link = inverse.OfPoint(tag_position)

        # ROOM LOCATION
        room_location = room.Location.Point

        print("========== ROOM LOCATION ==========")
        print("Room Location: {}".format(room_location))
        print("IsPointInRoom at location + 1ft: {}".format(
            room.IsPointInRoom(
                XYZ(
                    room_location.X,
                    room_location.Y,
                    room_location.Z + 1.0
                )
            )
        ))

        # BOUNDING BOX
        bbox = room.get_BoundingBox(None)

        print("========== XY COMPARISON ==========")

        if bbox is not None:

            print("Room Min: {}".format(bbox.Min))
            print("Room Max: {}".format(bbox.Max))
            print("Tag XY in link: {}, {}".format(
                point_link.X,
                point_link.Y
            ))

            inside_x = bbox.Min.X <= point_link.X <= bbox.Max.X
            inside_y = bbox.Min.Y <= point_link.Y <= bbox.Max.Y

            print("Inside X: {}".format(inside_x))
            print("Inside Y: {}".format(inside_y))

        # ELEVATIONS
        print("========== ELEVATIONS ==========")

        view = doc.GetElement(selected_tag.OwnerViewId)
        tag_level = view.GenLevel

        room_base_z = room.Level.Elevation + room.BaseOffset

        room_host_point = transform.OfPoint(
            XYZ(room_location.X, room_location.Y, room_base_z)
        )

        print("Tag Level Elevation: {}".format(tag_level.Elevation))
        print("Room Base Z in Link: {}".format(room_base_z))
        print("Room Base Z in Host: {}".format(room_host_point.Z))
        print("Room Height: {}".format(room.UnboundedHeight))


        #Original tag information
        tag_position = selected_tag.TagHeadPosition
        tag_type_id = selected_tag.GetTypeId()
        tag_view_id = selected_tag.OwnerViewId

        #Linked Room Reference
        room_reference = LinkElementId(selected_link.Id, selected_room_element.Id)

        #New Tag Position
        new_position = UV(
            tag_position.X,
            tag_position.Y
        )

    else:
        print("Selected Rooms: 0")

#==================================================
# TEST TRANSACTION
#==================================================   

    t = Transaction(doc, 'Reconcile Hosted Tag')
    t.Start()
    try:

        new_tag = doc.Create.NewRoomTag(
            room_reference,
            new_position,
            tag_view_id
        )

        if new_tag is None:
            raise Exception ("failed to create room tag")

        #Preserve original tag type
        new_tag.ChangeTypeId(tag_type_id)

        #Preserve tag Head Position
        new_tag.TagHeadPosition = tag_position

        doc.Regenerate()

        # Validate new Room reference
        new_reference = new_tag.TaggedRoomId

        if (new_reference.LinkInstanceId != selected_link.Id or
                new_reference.LinkedElementId != selected_room_element.Id):
            raise Exception("New tag is not associated with the selected Room.")

        if new_tag.IsOrphaned:
            raise Exception("New Room Tag is still orphaned.")

        #Store original tag ID before deletion
        old_tag_id = selected_tag.Id.Value

        #Delete Original
        deleted_ids = doc.Delete(selected_tag.Id)

        for deleted_id in deleted_ids:
            print("Deleted Element ID: {}".format(deleted_id.Value))

        print("Deleted elements: {}".format(len(deleted_ids)))

        #Commit
        commit_status = t.Commit()

        print("Commit status: {}".format(commit_status))

        if commit_status != TransactionStatus.Committed:
            print("WARNING: Transaction was not committed.")

        else:
            print("ROOM TAG RECONCILED SUCCESSFULLY")
            print("Old Tag ID: {}".format(old_tag_id))
            print("New Tag ID: {}".format(new_tag.Id.Value))

    except Exception as e:

        print("ORIGINAL ERROR: {}".format(str(e)))
        print("Transaction Status: {}".format(t.GetStatus()))

        if t.GetStatus() == TransactionStatus.Started:
            try:
                t.RollBack()
                print("Transaction rolled back.")

            except Exception as rollback_error:
                print("Rollback error: {}".format(rollback_error))

        else:
            print("Rollback skipped: Transaction is not Started.")

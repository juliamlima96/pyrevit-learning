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
#LIST INDEPENDENT TAGS
#==================================================

all_ind_tags = (
    FilteredElementCollector(doc)
    .OfClass(IndependentTag)
    .WhereElementIsNotElementType()
    .ToElements()
)

orphaned_ind_tags = []
orphaned_floor =[]
orphaned_ceiling =[]
orphaned_wall =[]

for tag in all_ind_tags:

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
        print("Tag {}, Category {} has no associated level".format(tag.Id.Value, tag.Category.Name))
        continue
        
    orphaned_ind_tags.append((tag, view, tag_level))

print("Total Independent Tags:", len(all_ind_tags))
print("Orphaned Independent Tags:", len(orphaned_ind_tags))
print("==================================================")

for tag, view, tag_level in orphaned_ind_tags:
    if tag.Category.Name == "Floor Tags":
        orphaned_floor.append((tag, view, tag_level))

    if tag.Category.Name == "Ceiling Tags":
        orphaned_ceiling.append((tag, view, tag_level))

    if tag.Category.Name == "Wall Tags":
        orphaned_wall.append((tag, view, tag_level))

for tag, view, tag_level in orphaned_floor:
    print("Tag ID: {} | Tag Category: {} | Tag Level: {}".format(tag.Id, tag.Category.Name, tag_level.Name))
print("Total Orphaned Floor Tags: ", len(orphaned_floor))
print("====================================================")

for tag, view, tag_level in orphaned_ceiling:
    print("Tag ID: {} | Tag Category: {} | Tag Level: {}".format(tag.Id, tag.Category.Name, tag_level.Name))
print("Total Orphaned Ceiling Tags: ", len(orphaned_ceiling))
print("====================================================")

for tag, view, tag_level in orphaned_wall:
    print("Tag ID: {} | Tag Category: {} | Tag Level: {}".format(tag.Id, tag.Category.Name, tag_level.Name))
print("Total Orphaned Wall Tags: ", len(orphaned_wall))
print("====================================================")

#==================================================
#LEVELS
#==================================================

all_levels = (FilteredElementCollector(doc).OfClass(Level).ToElements())
level_names = [level.Name for level in all_levels]

#==================================================
#COLLECT REVIT LINKS
#==================================================

linked_floors =[]
linked_ceilings =[]
linked_walls =[]

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

    #get floors in links         
    floors =(
        FilteredElementCollector(link_doc)
        .OfCategory(BuiltInCategory.OST_Floors)
        .WhereElementIsNotElementType()
        .ToElements()
    )

    ceilings =(
        FilteredElementCollector(link_doc)
        .OfCategory(BuiltInCategory.OST_Ceilings)
        .WhereElementIsNotElementType()
        .ToElements()
    )

    walls =(
        FilteredElementCollector(link_doc)
        .OfCategory(BuiltInCategory.OST_Walls)
        .WhereElementIsNotElementType()
        .ToElements()
    )

    for floor in floors:
        linked_floors.append((link, level_link, floor))

    for ceiling in ceilings:
        linked_ceilings.append((link, level_link, ceiling))

    for wall in walls:
        linked_walls.append((link, level_link, walls))

print ("Linked floors: ", len(linked_floors))
print ("Linked Ceilings: ", len(linked_ceilings))
print ("Linked Walls: ", len(linked_walls))
print("====================================================")

#==================================================
# MATCH  FLOOR TAGS AND LINKS BY LEVEL
#==================================================
for tag, view, tag_level in orphaned_floor:
    temp_floors = []
    matching_floors = []
    matching_floor_names = []

    selected_tag = tag

    #filter rooms by level
    for link, level_link, floor in linked_floors:   
        if tag_level.Name == level_link.Name:
            temp_floors.append((link, floor, level_link))

#==================================================
# MATCH TAGS AND FLOORS BY POSITION
#==================================================

    #Get tag position
    tag_position = selected_tag.TagHeadPosition

    #Get floor bounding box
    for link, floor, level_link in temp_floors:

        bbox = floor.get_BoundingBox(None)
        if bbox is None:
            continue

        #Compare tag position with room bounding box
        X_match = bbox.Min.X <= tag_position.X <= bbox.Max.X 
        Y_match = bbox.Min.Y <= tag_position.Y <= bbox.Max.Y

        if X_match and Y_match:
            matching_floors.append((link, floor ,level_link))

            floor_type = link_doc.GetElement(floor.GetTypeId())
            matching_floor_names.append(floor_type)
        
            print("MATCH FOUND")
            print("Tag ID: {}".format(selected_tag.Id.Value))
            print("Floor Type: {}".format(floor_type))
            print("Floor ID: {}".format(floor.Id.Value))
            print("Link ID: {}".format(link.Id.Value))
            print("Level: {}".format(level_link.Name))
            print("==================================================")
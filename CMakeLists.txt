cmake_minimum_required(VERSION 3.13.4)

project(DeepArcTimeline)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://www.dlr.de")
set(EXTENSION_CATEGORY """, Sequences")
set(EXTENSION_CONTRIBUTORS "Wadim Koslow (Deutsches Zentrum für Luft- und Raumfahrt e.V.), Philipp Rosauer (Deutsches Zentrum für Luft- und Raumfahrt e.V.), David Knapp (Deutsches Zentrum für Luft- und Raumfahrt e.V.), Jonas Levin Weber (Deutsches Zentrum für Luft- und Raumfahrt e.V.)")
set(EXTENSION_DESCRIPTION "This is the DeepArc Timeline extension for 3D Slicer.")
set(EXTENSION_ICONURL "https://www.dlr.de/favicon.ico")
set(EXTENSION_SCREENSHOTURLS "")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(DeepArcTimeline)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})

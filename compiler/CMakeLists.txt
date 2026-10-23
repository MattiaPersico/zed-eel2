cmake_minimum_required(VERSION 3.18)
project(eel2_check LANGUAGES C CXX)
include(FetchContent)
set(YSFX_PLUGIN OFF CACHE BOOL "" FORCE)
set(YSFX_GFX OFF CACHE BOOL "" FORCE)
set(YSFX_PORTABLE ON CACHE BOOL "" FORCE)
set(YSFX_TESTS OFF CACHE BOOL "" FORCE)
set(YSFX_TOOLS OFF CACHE BOOL "" FORCE)
# Upstream's generated-assembly check assumes it is the top-level project.
# Source and generated assembly are both pinned by the commit below.
set(YSFX_SKIP_CHECKSUM ON CACHE BOOL "" FORCE)
FetchContent_Declare(ysfx
  GIT_REPOSITORY https://github.com/jpcima/ysfx.git
  GIT_TAG 8077347ccf4115567aed81400281dca57acbb0cc
  GIT_SUBMODULES thirdparty/dr_libs)
FetchContent_MakeAvailable(ysfx)
add_executable(eel2-check main.cpp)
target_link_libraries(eel2-check PRIVATE ysfx)
target_compile_features(eel2-check PRIVATE cxx_std_11)

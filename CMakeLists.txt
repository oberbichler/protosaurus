cmake_minimum_required(VERSION 3.15...3.26)

project(protosaurus LANGUAGES CXX)

if (NOT SKBUILD)
  message(WARNING "\
  This CMake file is meant to be executed using 'scikit-build'. Running
  it directly will almost certainly not produce the desired result. If
  you are a user trying to install this package, please use the command
  below, which will install all necessary build dependencies, compile
  the package in an isolated environment, and then install it.
  =====================================================================
   $ pip install .
  =====================================================================
  If you are a software developer, and this is your own package, then
  it is usually much more efficient to install the build dependencies
  in your environment once and use the following command that avoids
  a costly creation of a new virtual environment at every compilation:
  =====================================================================
   $ pip install nanobind scikit-build-core[pyproject]
   $ pip install --no-build-isolation -ve .
  =====================================================================
  You may optionally add -Ceditable.rebuild=true to auto-rebuild when
  the package is imported. Otherwise, you need to re-run the above
  after editing C++ files.")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)
set(CMAKE_POSITION_INDEPENDENT_CODE on)

find_package(Python 3.8
  REQUIRED COMPONENTS Interpreter Development.Module
  OPTIONAL_COMPONENTS Development.SABIModule)

find_package(nanobind CONFIG REQUIRED)

set(protobuf_MSVC_STATIC_RUNTIME off)

include(cmake/CPM.cmake)

CPMAddPackage("gh:protocolbuffers/protobuf@23.3")

nanobind_add_module(
  protosaurus_ext
  STABLE_ABI
  NB_STATIC
  src/protosaurus_ext.cpp
)

target_include_directories(
  protosaurus_ext
  PRIVATE
  include
)

target_link_libraries(
  protosaurus_ext
  PRIVATE
  protobuf::libprotobuf
)

install(TARGETS protosaurus_ext LIBRARY DESTINATION protosaurus)

#!/bin/bash

c_compiler="clang"
cxx_compiler="clang++"
use_conan="false"
use_conda="false"
build_type="RelWithDebInfo"

echo "args = $@"

for arg in "$@"; do 
  case "$arg" in
    "gcc")
      c_compiler="gcc"
      cxx_compiler="g++"
      ;;

    "clang")
      c_compiler="clang"
      cxx_compiler="clang++"
      ;;

    "clang-10")
      c_compiler="clang-10"
      cxx_compiler="clang++-10"
      ;;
    
    "debug")
      build_type="Debug"
      ;;

    "release")
      build_type="Release"
      ;;

    "conan")
      use_conan="true"
      ;;

    "conda")
      use_conda="true"
      ;;

    esac
done

echo "Using CC=$c_compiler, CXX=$cxx_compiler"

build_dir="$c_compiler-$build_type"
cmake_opts="-DCMAKE_C_COMPILER=$c_compiler -DCMAKE_CXX_COMPILER=$cxx_compiler -DCMAKE_BUILD_TYPE=$build_type -DKATANA_LANG_BINDINGS=python"

if [[ $use_conda == "true" ]]; then
  build_dir="$build_dir-conda"
fi

if [[ $use_conan == "true" ]]; then
  build_dir="$build_dir-conan"
  cmake_opts="$cmake_opts -DKATANA_AUTO_CONAN=1"
fi

cmake_cmd="cmake -S . -B $build_dir $cmake_opts"
echo "cmake command: $cmake_cmd"



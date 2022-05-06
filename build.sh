#!/bin/bash

c_compiler="clang"
cxx_compiler="clang++"
use_conan="false"
use_conda="false"
build_type="RelWithDebInfo"
cmake_extra_args=""

echo "args = $@"



while [[ $# -gt 0 ]] ; do 
  case "$1" in
    "gcc")
      c_compiler="gcc"
      cxx_compiler="g++"
      shift
      ;;

    "clang-12")
      c_compiler="clang-12"
      cxx_compiler="clang++-12"
      shift
      ;;

    "clang")
      c_compiler="clang"
      cxx_compiler="clang++"
      shift
      ;;
    
    "debug")
      build_type="Debug"
      shift
      ;;

    "release")
      build_type="Release"
      shift
      ;;

    "conan")
      use_conan="true"
      shift
      ;;

    "conda")
      use_conda="true"
      shift
      ;;
    *)
      cmake_extra_args="$cmake_extra_args $1"
      shift
      ;;

    esac
done

echo "Using CC=$c_compiler, CXX=$cxx_compiler"

build_dir="$c_compiler-$build_type"
cmake_opts="-DCMAKE_C_COMPILER=$c_compiler -DCMAKE_CXX_COMPILER=$cxx_compiler -DCMAKE_BUILD_TYPE=$build_type -DCMAKE_EXPORT_COMPILE_COMMANDS=1 $cmake_extra_args"

if [[ $use_conda == "true" ]]; then
  cmake_opts="$cmake_opts -DKATANA_LANG_BINDINGS=python"
  build_dir="$build_dir-conda"
fi

if [[ $use_conan == "true" ]]; then
  build_dir="$build_dir-conan"
  cmake_opts="$cmake_opts -DCMAKE_TOOLCHAIN_FILE=conan_paths.cmake"
fi

src_dir=".."

if [[ $use_conan == "true" ]]; then
  conan_cmd="conan install -if . --build=missing $src_dir/config/conanfile.py"
  cmake_cmd="mkdir -p $build_dir && cd $build_dir && $conan_cmd && cmake -S $src_dir -B . $cmake_opts"
else
  cmake_cmd="mkdir -p $build_dir && cd $build_dir && cmake -S $src_dir -B . $cmake_opts"

fi


echo "cmake command: $cmake_cmd"

eval $cmake_cmd
# eval $cmake_cmd && cd $build_dir && make -j 8 



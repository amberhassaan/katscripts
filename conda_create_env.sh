#!/bin/bash

name="kat"
repo="$PWD"
condaroot="$HOME/miniconda3"

source $condaroot/etc/profile.d/conda.sh

conda config --add channels conda-forge
# For library compatibility reasons, prefer taking dependencies from
# higher priority channels even if newer versions exist in lower priority
# channels.
conda config --set channel_priority strict

conda deactivate
#install mamba if not found
install_base_pkgs=""
mamba_found=0
if $(conda list | grep mamba 2>&1 > /dev/null); then
  echo 'mamba found'
  mamba_found=1
else
  install_base_pkgs="mamba"
fi

if $(conda list | grep 'conda.lock' 2>&1 > /dev/null); then
  echo 'mamba found'
else
  install_base_pkgs="$install_base_pkgs conda-lock"
fi

if [[ $mamba_found -eq 1 ]]; then 
  mamba install $install_base_pkgs -n base -c conda-forge
else
  conda install $install_base_pkgs -n base -c conda-forge
fi

#create environment
# assuming that external/katana/conda-lock.yml is subsumed by conda-lock.yml
# $condaroot/bin/conda-lock install -n $name  $repo/external/katana/conda-lock.yml
$condaroot/bin/conda-lock install -n $name $repo/conda-lock.yml

source $HOME/miniconda3/etc/profile.d/mamba.sh

mamba activate $name
mamba install numactl-devel-cos7-x86_64 # For x86_64 builds
mamba deactivate



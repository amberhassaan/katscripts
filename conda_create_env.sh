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
#install mamba
conda install conda-lock mamba -n base -c conda-forge

#create environment
$condaroot/bin/conda-lock install -n $name $repo/conda-lock.yml
$condaroot/bin/conda-lock install -n $name  $repo/external/katana/conda-lock.yml

source $HOME/miniconda3/etc/profile.d/mamba.sh

mamba activate $name
mamba install numactl-devel-cos7-x86_64 # For x86_64 builds
mamba deactivate



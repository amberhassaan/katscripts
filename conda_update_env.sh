#!/bin/bash

name="kat"
repo="$PWD"
condaroot="$HOME/miniconda3"

source $condaroot/etc/profile.d/conda.sh

$condaroot/bin/conda-lock install -n $name  $repo/external/katana/conda-lock.yml
$condaroot/bin/conda-lock install -n $name  $repo/conda-lock.yml



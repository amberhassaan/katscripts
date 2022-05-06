#!/bin/bash

name="kat"
repo="$PWD"

source $HOME/miniconda3/etc/profile.d/conda.sh

conda env remove -n $name

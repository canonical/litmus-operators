#!/usr/bin/env bash

# run this from the project root
for component in auth backend chaoscenter
do
  # remove the lib to get rid of the source override
  VIRTUAL_ENV="" uv --directory $component remove litmus_libs
  # add it back to pull the most recent pypi version
  VIRTUAL_ENV="" uv --directory $component add litmus_libs
done

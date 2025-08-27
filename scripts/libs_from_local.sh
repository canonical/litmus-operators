#!/usr/bin/env bash

# run this from the project root
uv build ./libs
for component in auth backend chaoscenter
do
  [[ -d ./$component/wheels ]] || mkdir ./$component/wheels
  cp -r libs/dist/litmus_libs-0.0.2-py3-none-any.whl $component/wheels/litmus_libs-0.0.2-py3-none-any.whl
  VIRTUAL_ENV="" uv --directory $component add wheels/litmus_libs-0.0.2-py3-none-any.whl
done

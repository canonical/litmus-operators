#!/usr/bin/env bash
# run this from the project root

# this will rebuild the libs, mount the wheel in each component's /wheels directory,
# and update the lockfiles

rm -rf ./libs/dist
uv build ./libs
for component in auth backend chaoscenter
do
  [[ -d ./$component/wheels ]] || mkdir ./$component/wheels
  cp -r libs/dist/litmus_libs-0.0+dev-py3-none-any.whl $component/wheels/
  VIRTUAL_ENV="" uv --directory $component add wheels/litmus_libs-0.0+dev-py3-none-any.whl --refresh
done

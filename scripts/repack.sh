#!/usr/bin/env bash

# run this from the project root
for component in auth backend chaoscenter;
do
  charmcraft -v pack -p $component -o $component
#  mv ./*.charm $component
done

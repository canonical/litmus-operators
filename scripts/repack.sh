#!/usr/bin/env bash

# run this from the project root
for component in auth backend chaoscenter;
do
  charmcraft pack -p $component -o $component
done

#!/usr/bin/env bash

jhack deploy auth auth
jhack deploy backend backend
jhack deploy chaoscenter chaoscenter

juju relate auth backend
juju relate auth chaoscenter
juju relate backend chaoscenter

juju deploy mongodb-k8s mongo
juju relate mongo auth
juju relate mongo backend
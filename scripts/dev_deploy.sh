#!/usr/bin/env bash

jhack deploy auth auth -- --trust
jhack deploy backend backend -- --trust
jhack deploy chaoscenter chaoscenter -- --trust

juju relate auth backend
juju relate auth chaoscenter
juju relate backend chaoscenter

juju deploy mongodb-k8s mongo --trust
juju relate mongo auth
juju relate mongo backend

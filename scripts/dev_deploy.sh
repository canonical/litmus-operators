#!/usr/bin/env bash

jhack deploy auth auth -- --trust
jhack deploy backend backend -- --trust
jhack deploy chaoscenter chaoscenter -- --trust

SECRET_ID=$(juju add-secret cc-users admin-password=litmus charm-password=charm)
juju grant-secret cc-users chaoscenter
juju config chaoscenter user_secrets="$SECRET_ID"

juju relate auth backend
juju relate auth chaoscenter
juju relate backend chaoscenter

juju deploy mongodb-k8s mongo --trust
juju relate mongo auth
juju relate mongo backend

#!/usr/bin/env bash

jhack deploy auth auth -- --trust
jhack deploy backend backend -- --trust
jhack deploy chaoscenter chaoscenter -- --trust

ADMIN_PWD="Admin1!pass"
CHARM_PWD="Charm1!pass"
SECRET_ID=$(juju add-secret cc-users admin-password=$ADMIN_PWD charm-password=$CHARM_PWD)
juju grant-secret cc-users chaoscenter
juju config chaoscenter user_secrets="$SECRET_ID"

juju relate auth backend
juju relate auth chaoscenter
juju relate backend chaoscenter

juju deploy mongodb-k8s mongo --trust
juju relate mongo auth
juju relate mongo backend

echo "All done! Wait for idle."
echo "  credentials: admin/$ADMIN_PWD, charm/$CHARM_PWD"
#!/bin/bash
cd /var/www/economy_web/economy_web || exit 1
git fetch origin
git reset --hard origin/main
sudo systemctl restart economy

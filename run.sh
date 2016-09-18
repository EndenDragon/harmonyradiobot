#!/bin/bash
while true; do
    sleep 2;
    echo "Running Bot..";
    python3.5 main.py;
    ret=$?
    if [ "$ret" = "2" ]; then
       echo "Running git update task"
       git reset --hard
       git pull
       chmod a+x ./run.sh
    fi
    echo "Bot exited"
done

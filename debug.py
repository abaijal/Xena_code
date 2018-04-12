#!/usr/bin/python
import os
xena_debug = True

def debug(module, string):
    if xena_debug:
        print "[" + module.__name__ + "]: " + string
def envtoarray(env_name, stringed=True):
    array=[]
    for x in os.environ[env_name].replace(' ','').split(',') :
        if stringed:
            array.append(x)
        else:
            array.append(int(x))
    return array

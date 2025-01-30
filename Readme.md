### Installation instructions for Windows

## Create virtual environment

python3 -m venv env

## Activate environment

env/scripts/activate


## Install libraries

pip install -r requirements.txt

##  create tables using migrations 

python manage.py makemigrations

python manage.py migrate

## start server locally

python manage.py runserver 

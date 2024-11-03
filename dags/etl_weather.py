from airflow import DAG
from airflow.providers.http.hooks.http import HttpHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.decorators import task
from airflow.utils.dates import days_ago
import requests
import json



# new york city
LATITUDE = 40.7128
LONGITUDE = 74.0060

POSTGRES_CONN_ID = 'postgres_default'
API_CONNECTION_ID = "open_meteo_api"

default_args = {
    'owner' : 'airflow',
    'start_date' : days_ago(1)
}

## DAG
with DAG(dag_id='weather_etl_pipeline',
         default_args=default_args,
         schedule_interval='@daily',
         catchup=False) as dags:
    @task()
    def extract_weather_data():
         # get the connection for the api
         http_hook=HttpHook(http_conn_id=API_CONN_ID,method='GET')
         # url = ## https://api.open-meteo.com/
         endpoint=f'/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&current_weather=true'
         response=http_hook.run(endpoint) # making request using this

         if response.status_code == 200:
             data = response.json()
             return data
         else:
             print(f"Error: {response.status_code} - {response.reason}")
    @task()
    def transform_weather_data(weather_data):

        # this is the transform to convert this into key value pairs that we will later store in postgres
        current_weather = weather_data['current_weather']
        transformed_data = {
            'latitude': LATITUDE,
            'longitude': LONGITUDE,
            'temperature': current_weather['temperature'],
            'windspeed': current_weather['windspeed'],
            'winddirection': current_weather['winddirection'],
            'weathercode': current_weather['weathercode']
        }
        return transformed_data
    
    @task()
    def load_weather_data(transformed_data):
        # this is the load to store the data in postgres
        pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_data (
            latitude FLOAT,
            longitude FLOAT,
            temperature FLOAT,
            windspeed FLOAT,
            winddirection FLOAT,
            weathercode INT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("""
        INSERT INTO weather_data (latitude, longitude, temperature, windspeed, winddirection, weathercode)
        VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            transformed_data['latitude'],
            transformed_data['longitude'],
            transformed_data['temperature'],
            transformed_data['windspeed'],
            transformed_data['winddirection'],
            transformed_data['weathercode']
        ))

        conn.commit()
        cursor.close()




    # data workflow from DAG and execute this in the form of a pipeline
    
    weather_data= extract_weather_data()
    transformed_data=transform_weather_data(weather_data)
    load_weather_data(transformed_data)
# lakehouse

A local data lakehouse that runs on minikube. MinIO provides S3-compatible object storage, Apache Iceberg is the table format, and Lakekeeper serves as the Iceberg REST catalog. Trino is the SQL query engine. dbt handles transformations and Dagster orchestrates the pipelines. Later phases add a Cube semantic layer and LangGraph-based chatbots on top of the modelled data.

import pyarrow.parquet as pq

file = "train.parquet"

table = pq.ParquetFile(file)

print("Rows:", table.metadata.num_rows)
print("Columns:", table.metadata.schema.names)
print(table.schema) 

batch = next(table.iter_batches(batch_size=1000))

df = batch.to_pandas()

print(df.head())
print(df.shape)
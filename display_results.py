import plotly.express as px
import pandas as pd

# Path to your CSV file
solution_path = '/Users/esmerubinstein/Desktop/solution.csv'

# Read the CSV file into a DataFrame
df = pd.read_csv(solution_path)

# Filter out rows where Start and End are 0 (if necessary)
df = df[(df['Start'] != 0) | (df['End'] != 0)]

# Define an epoch date (example: 2020-01-01)
epoch_date = pd.to_datetime('2020-01-01')

# # Convert integer days to datetime objects
df['Start_dt'] = epoch_date + pd.to_timedelta(df['Start'], unit='s')
df['End_dt'] = epoch_date + pd.to_timedelta(df['End'], unit='s')

print(df['Start'])

# Plot with px.timeline
fig = px.timeline(df, x_start="Start_dt", x_end="End_dt", y="Worker", color="TaskType", text = "Task",
                  hover_data= {"Task": True, "Worker": False, "TaskType": False, "Start_dt": False, "End_dt": False, 
                               "Start": True, "End": True})

# Update layout if needed
fig.update_layout(
    title="Schedule",
    xaxis_title="Time",
)
# Show the plot
print(fig)
fig.show()

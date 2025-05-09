import plotly.express as px
import pandas as pd

# Path to your CSV file
solution_path = '/Users/esmerubinstein/Desktop/ai_caring_updated2.csv'

# Read the CSV file into a DataFrame
df = pd.read_csv(solution_path)

# Filter out rows where Start and End are 0 (if necessary)
df = df[(df['Start'] != 0) | (df['End'] != 0)]

# Define an epoch date (example: 2020-01-01)
epoch_date = pd.to_datetime('2020-01-01')

# # Convert integer days to datetime objects
df['Start_dt'] = epoch_date + pd.to_timedelta(df['Start'], unit='s')
df['End_dt'] = epoch_date + pd.to_timedelta(df['End'], unit='s')

# if df['Task'] contains the word 'break' no caps, set new column type to 1
# if df['Task'] == 'travel' set new column type to 2
# else set to 0
df['Type'] = 0
df.loc[df['Task'].str.contains('break'), 'Type'] = 1
df.loc[df['Task'] == 'travel', 'Type'] = 2
df['Worker'] = df['Worker'].astype(str)  # Ensure Worker column is of type string
df = df.sort_values('Worker')

# Plot with px.timeline
fig = px.timeline(df, x_start="Start_dt", x_end="End_dt", y="Worker", color="Type", text = "Task",
                  hover_data= {"Task": True, "Worker": False,"Start_dt": False, "End_dt": False, 
                               "Start": True, "End": True, "Skill": True, "Type": False},)

# Update layout if needed
fig.update_layout(
    title="Schedule",
    xaxis_title="Time",
)

for trace in fig.data:
    if 'text' in trace:
        trace.textposition = 'inside'

# # add text box to the figure with total slack and total preference
# fig.add_annotation(
#     text="Total Slack: " + str(totalSlack),
#     xref="paper", yref="paper",
#     x=0.01, y=0.99,
#     showarrow=False,
#     font=dict(
#         family="Courier New, monospace",
#         size=16,
#         color="#ffffff"
#     ),
#     align="left",
#     bordercolor="#c7c7c7",
#     borderwidth=2,
#     borderpad=4,
#     bgcolor="black",
#     opacity=0.8
# )

# fig.add_annotation(
#     text="Total Preference: " + str(totalPreference),
#     xref="paper", yref="paper",
#     x=0.01, y=0.94,
#     showarrow=False,
#     font=dict(
#         family="Courier New, monospace",
#         size=16,
#         color="#ffffff"
#     ),
#     align="left",
#     bordercolor="#c7c7c7",
#     borderwidth=2,
#     borderpad=4,
#     bgcolor="black",
#     opacity=0.8
# )
fig.show()

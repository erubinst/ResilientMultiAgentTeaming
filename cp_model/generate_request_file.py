import pandas as pd
from config import DATA_PATH, SCENARIO
import json


def expand_row(row):
    multiplier = row.get("multiplier")
     
    if pd.isna(multiplier) or str(multiplier).strip() == "":
        return row.to_frame().T 
    
    days = [day.strip() for day in str(multiplier).split(",")]
    
    if not days:
        return row.to_frame().T

    expanded_df = pd.DataFrame([row] * len(days)).copy()
    expanded_df["templates"] = [f"{row['templates']}_{day}" for day in days]
    expanded_df["subtasks"] = [f"{row['subtasks']}_{day.lower()}" for day in days]
    
    return expanded_df


def expand_templates(templates_df):
    """
    Expand the templates DataFrame by creating a new row for each day in the multiplier column.
    """
    expanded_dfs = templates_df.apply(expand_row, axis=1)
    expanded_df = pd.concat(expanded_dfs.tolist(), ignore_index=True)

    return expanded_df


def generate_capability_df(resources_df):
    # Split capabilities and explode to get one capability per row
    df_exploded = resources_df['capabilities'].str.split(', ').explode()

    unique_capabilities = pd.DataFrame({
        'capability': sorted(df_exploded.unique()),
    })
    # unique_capabilities['id'] = range(1, len(unique_capabilities) + 1)

    return unique_capabilities


def add_capability_ids_to_resources(resources_df, capabilities_df):
    resources_df['capability'] = resources_df['capabilities'].str.split(', ')
    resources_df = resources_df.explode('capability')
    resources_df = resources_df.merge(capabilities_df, on='capability', how='left')
    resources_df = resources_df.groupby(['name', 'capabilities', 'location'])['id'].apply(list).reset_index()
    resources_df['capabilities'] = resources_df['capabilities'].str.split(', ')
    resources_df.rename(columns={'id': 'capability_ids'}, inplace=True)

    return resources_df



def assign_capability_ids(templates_df, capabilities_df):
    """
    Assign capability IDs, Subtask IDs, and Template IDs to the templates
    """
    # original_columns = templates_df.columns.tolist()
    # templates_df['capability'] = templates_df['requiredCapabilities'].str.split(', ')
    # templates_df = templates_df.explode('capability')
    # templates_df = templates_df.merge(capabilities_df, how='left', on='capability')
    # group_cols = [col for col in original_columns]
    # required_ids_df = templates_df.groupby(group_cols)['id'].apply(list).reset_index()
    # templates_df = templates_df.merge(required_ids_df, on=group_cols)
    templates_df["start-location"] = templates_df["start-location"].fillna("@start-location")
    templates_df["end-location"] = templates_df["end-location"].fillna("@end-location")

    # assign subtask and template IDs
    # templates_df["id"] = range(1, len(templates_df) + 1)
    # unique_subtasks = {subtask: i + 1 for i, subtask in enumerate(sorted(templates_df["subtasks"].unique()))}
    # templates_df["subtask_id"] = templates_df["subtasks"].map(unique_subtasks)
    templates_df["requiredCapabilities"] = templates_df["requiredCapabilities"].astype(str).str.replace(" ", "").str.split(",")
    # templates_df["requiredCapabilityIds"] = templates_df["requiredCapabilityIds"].astype(str).str.split(",")

    return templates_df


def create_templates_json(templates_df):
    """
    Create the templates JSON structure from the templates DataFrame.
    """
    templates_list = []

    for template_name, group in templates_df.groupby("templates"):
        
        subtasks = []
        for _, row in group.iterrows():
            subtask = {
                "taskName": row["subtasks"],
                "type": "executable",
                "requiredCapabilities": row["requiredCapabilities"],
                "duration": int(row["duration"]),
                "start-location": row["start-location"],
                "end-location": row["end-location"],
                "explicit_transport_task": bool(row["explicit_transport_task"])
            }
            subtasks.append(subtask)
        
        template_entry = {
            "name": template_name,
            "type": "meets",
            "requiredCapabilities": [],
            "subtasks": subtasks
        }
        templates_list.append(template_entry)

    # Final dictionary
    result_dict = {"templates": templates_list}
    return result_dict


def create_orders_json(templates_df):
    """
    Create the orders dictionary from the templates DataFrame.
    """
    unique_df = (
        templates_df.sort_values("templates")             # optional: deterministic order
        .drop_duplicates(subset="templates", keep="first")
    )
    unique_df['order_multiplier'] = unique_df['order_multiplier'].str.split(', ')
    unique_df = unique_df.explode("order_multiplier", ignore_index=True)
    unique_df["order_multiplier"] = unique_df["order_multiplier"].fillna("")  # fill NaN with empty string
    orders = []
    for _, row in unique_df.iterrows():
        # name should be row plus multiplier
        orders.append({
            "name":              row['templates'] + ("_" + row["order_multiplier"] if row["order_multiplier"] else ""),
            "quantity":          1,
            "earlieststartdate": "",            # left blank per your spec
            "duedate":           "",            # left blank per your spec
            "start-location":    row['order_start'],
            "end-location":      row['order_end'],
            "tasks":             [row["templates"]],
            "optional":          False
        })

    orders_dict = {"orders": orders}
    return orders_dict


def create_resources_json(resources_df):
    """
    Create the resources dictionary from the resources DataFrame.
    """
    resources_list = []
    resources = []
    for _, row in resources_df.iterrows():
        resource_entry = {
            "name": row["name"],
            "type": "resusable",
            "capabilities": row["capabilities"].split(", "),
            "location": row["location"]
        }
        resources_list.append(resource_entry)
        resource = {
            "name": row["name"],
            "type": row["name"],
            "downtimes": [],
        }
        resources.append(resource)

    resources_dict = {"resources": resources}
    resourceTypes_dict = {"resourceTypes": resources_list}
    json_dict = {**resourceTypes_dict, **resources_dict}
    return json_dict


def extract_travel_matrix(travel_csv):
    """
    Extract the travel matrix from the CSV file.
    """
    travel_df = pd.read_csv(travel_csv, index_col=0)

    distance_dict = travel_df.to_dict(orient='index')
    return distance_dict


def main():
    resources_df = pd.read_csv(DATA_PATH + SCENARIO + "/request_csv/resources.csv")
    templates_df = pd.read_csv(DATA_PATH + SCENARIO + "/request_csv/templates.csv")
    capabilities_df = generate_capability_df(resources_df)
    # resources_df = add_capability_ids_to_resources(resouces_df, capabilities_df)
    # templates_df = expand_templates(templates_df)
    templates_df = assign_capability_ids(templates_df, capabilities_df)
    templates_dict = create_templates_json(templates_df)
    resources_dict = create_resources_json(resources_df)

    orders_dict = create_orders_json(templates_df)
    full_json = {**resources_dict, **templates_dict, **orders_dict}
    file_path = DATA_PATH + SCENARIO + "/request_json"
    with open(file_path + "/request.json", "w") as f:
        json.dump(full_json, f, indent=4)
    print("Request file generated successfully at:", file_path + "/request.json")

    travel_matrix = extract_travel_matrix(DATA_PATH + SCENARIO + "/request_csv/travel_matrix.csv")
    with open(file_path + "/travel_matrix.json", "w") as f:
        json.dump(travel_matrix, f, indent=4)
    print("Travel matrix file generated successfully at:", DATA_PATH + SCENARIO + "/request_json/travel_matrix.json")

main()
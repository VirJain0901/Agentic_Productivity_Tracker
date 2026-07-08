import dash
from dash import dcc, html #dash core concepts html for layout
import plotly.express as px
import plotly.graph_objects as go
import os
import sys
import django
import pandas as pd

#Django setup for importing the models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "employee_tracker.settings")
django.setup()

from django.utils import timezone
from monitoring.models import IdleTime, ProductiveAppUsage, Session


today = timezone.localtime().date()


app = dash.Dash(__name__)
app.title = "Employee Monitoring Dashboard"


employee_id = 2  # temporary need to add dropdown of employees

# Idle time query set for a day
idle_qs = IdleTime.objects.filter(
    employee_id=employee_id,
    start_time__date=today
).values("start_time", "end_time", "total_idle_sec")
idle_df = pd.DataFrame(list(idle_qs))

# Session for a day
session_qs = Session.objects.filter(
    employee_id=employee_id,
    start_time__date=today
).values("start_time", "end_time")
session_df = pd.DataFrame(list(session_qs))

# Productive app usage
apps_qs = ProductiveAppUsage.objects.filter(employee_id=employee_id).values(
    "app_name", "total_time_sec"
)
apps_df = pd.DataFrame(list(apps_qs))
if not apps_df.empty:
    apps_df["total_time_min"] = apps_df["total_time_sec"] / 60

# graph 1 session + idle time
timeline_data = []

if not session_df.empty:
    session_start = session_df["start_time"].min()
    session_end = session_df["end_time"].max()

    # Productive block
    timeline_data.append(dict(Task="Work Session", Start=session_start, Finish=session_end, Status="Active")) #Createing a task block labeled "Work Session" with Status="Active"

    # Idle blocks
    for _, row in idle_df.iterrows():
        timeline_data.append(dict(Task="Work Session", Start=row["start_time"], Finish=row["end_time"], Status="Idle"))

timeline_df = pd.DataFrame(timeline_data)

# Graph 1: Timeline idle vs active
fig1 = px.timeline(
    timeline_df,
    x_start="Start",
    x_end="Finish",
    y="Task",
    color="Status",
    color_discrete_map={"Idle": "tomato", "Active": "mediumseagreen"},
    template="plotly_dark"
)
fig1.update_layout(
    title="Timeline of Idle vs Active Periods",
    xaxis_title="Time",
    yaxis_title="",
    plot_bgcolor="black", #plot_bgcolor  the area inside the plotting area graph bg 
    paper_bgcolor="black" #paper_bgcolor  the area outside the plotting area overall bg

)

# Graph 2: Pie Chart total idle vs total productive
idle_total_min = idle_df["total_idle_sec"].sum() / 60 if not idle_df.empty else 0
productive_total_min = apps_df["total_time_min"].sum() if not apps_df.empty else 0

fig2 = go.Figure(data=[go.Pie(
    labels=["Idle Time (min)", "Productive Time (min)"],
    values=[idle_total_min, productive_total_min],
    hole=0.4
)])
fig2.update_layout(
    title="Idle vs Productive Time",
    template="plotly_dark",
    plot_bgcolor="black",
    paper_bgcolor="black"
)

#Graph 3: Bar Chart
fig3 = px.bar(
    apps_df,
    x="app_name",
    y="total_time_min",
    labels={"app_name": "Applications", "total_time_min": "Time (minutes)"},
    title="Time Spent on Productive Apps",
    color="total_time_min",
    color_continuous_scale=px.colors.sequential.Viridis,
    template="plotly_dark"
)
fig3.update_layout(
    plot_bgcolor="black",
    paper_bgcolor="black"
)

#  Layout
app.layout = html.Div(style={"backgroundColor": "black", "padding": "20px"}, children=[
    html.H1("Employee Productivity Dashboard", style={"textAlign": "center", "color": "white"}),
    dcc.Graph(figure=fig1),
    dcc.Graph(figure=fig2),
    dcc.Graph(figure=fig3),
])

if __name__ == "__main__":
    app.run(debug=True)

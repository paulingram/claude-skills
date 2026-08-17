import bauplan


@bauplan.model()
@bauplan.python('3.11')
def trips_clean(data=bauplan.Model('taxi_trips')):
    return data

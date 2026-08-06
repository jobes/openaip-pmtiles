# ISO country codes that define the processing workload.
# Currently restricted to SK, CZ, HU only.
countries = ['sk', 'cz', 'hu']

# this features are too slow to generate, they will be excluded from final pmtiles
slow_features = {'ar': {
    'airspaces': {'name':['FIR COMODORO']},
    'airspaces_border_offset': {'name':['FIR COMODORO']},
    'airspaces_border_offset_2x': {'name':['FIR COMODORO']}
    },'au': {
    'airspaces': {'name':['MELBOURNE FIR CTA A2']},
    'airspaces_border_offset': {'name':['MELBOURNE FIR CTA A2']},
    'airspaces_border_offset_2x': {'name':['MELBOURNE FIR CTA A2']}
    },'gl': {
    'airspaces': {'name':['NUUK SECTOR NORTH', 'BGGL FIR']},
    'airspaces_border_offset': {'name':['NUUK SECTOR NORTH', 'BGGL FIR']},
    'airspaces_border_offset_2x': {'name':['NUUK SECTOR NORTH', 'BGGL FIR']}
    }
    }


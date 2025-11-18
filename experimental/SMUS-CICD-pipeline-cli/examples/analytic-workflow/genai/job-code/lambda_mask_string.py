def lambda_handler(event, context):
    """Lambda handler for mask_string function."""
    input_string = event.get('input_string', '')
    
    if len(input_string) <= 4:
        return {'result': input_string}
    else:
        masked = "*" * (len(input_string) - 4) + input_string[-4:]
        return {'result': masked}

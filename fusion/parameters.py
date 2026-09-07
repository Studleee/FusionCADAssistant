"""User-parameter helpers.

Creates or updates Fusion user parameters so dimensions stay editable
from Modify > Change Parameters.
"""

import adsk.core

from geometry.parameters import validate_parameter_name


def set_user_parameter(design, name, value_cm, units='mm', comment=''):
    """Create or update a user parameter.

    value_cm: numeric value in Fusion internal centimeters.
    units: unit string stored with the parameter (typically 'mm').

    Returns the UserParameter.
    """
    validate_parameter_name(name)
    params = design.userParameters
    existing = params.itemByName(name)

    if units == 'mm':
        expression = '{} mm'.format(float(value_cm) * 10.0)
    else:
        expression = str(float(value_cm))

    value_input = adsk.core.ValueInput.createByString(expression)

    if existing:
        existing.expression = expression
        if comment:
            existing.comment = comment
        return existing

    param = params.add(name, value_input, units, comment)
    if not param:
        raise RuntimeError('Failed to create user parameter {!r}.'.format(name))
    return param


def link_dimension_to_parameter(dimension, parameter_name):
    """Drive a sketch dimension from a named user parameter."""
    validate_parameter_name(parameter_name)
    if not dimension or not dimension.parameter:
        raise RuntimeError('Dimension has no model parameter to link.')
    dimension.parameter.expression = parameter_name

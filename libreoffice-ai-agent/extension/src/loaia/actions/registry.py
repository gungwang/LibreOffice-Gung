from loaia.actions.app import APP_ACTIONS
from loaia.actions.base_actions import BASE_ACTIONS
from loaia.actions.calc import CALC_ACTIONS
from loaia.actions.draw import DRAW_ACTIONS
from loaia.actions.impress import IMPRESS_ACTIONS
from loaia.actions.math_actions import MATH_ACTIONS
from loaia.actions.writer import WRITER_ACTIONS

ACTION_REGISTRY = {
    action.tool_id: action
    for action in [
        *WRITER_ACTIONS,
        *CALC_ACTIONS,
        *IMPRESS_ACTIONS,
        *DRAW_ACTIONS,
        *MATH_ACTIONS,
        *BASE_ACTIONS,
        *APP_ACTIONS,
    ]
}

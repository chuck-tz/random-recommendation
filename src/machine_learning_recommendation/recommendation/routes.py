from flask import request, Blueprint
from machine_learning_recommendation.recommendation.filters import (
    fetch_shifts_start_end_created,
    fetch_busy_users,
    fetch_unavailable_users,
    fetch_ineligible_users,
    fetch_no_work_hrs,
)
import requests
import json
import os
import logging
from datetime import datetime
from machine_learning_recommendation.recommendation.utils import (
    get_arg_or_default,
    get_error_return,
    machine_learning_query,
    lists_union,
    object_and_200,
    get_user_ids,
    lists_difference,
    list_shuffle,
    concoct,
)

recommendation = Blueprint("recommendation", __name__)


@recommendation.route("/api/health-check", methods=["GET"])
def health_check():
    logger = logging.getLogger(__name__)
    logger.info("health_check")

    return (
        json.dumps({"success": True}),
        200,
        {"ContentType": "application/json"},
    )


@recommendation.route("/api/ml/v1/recommendation", methods=["GET"])
def recommend_and_return():
    logger = logging.getLogger(__name__)
    logger.info("recommend_and_return")

    number_to_return = get_arg_or_default("limit", int, 10)
    ml_recommend = get_arg_or_default("ml-recommend", int, 0)
    ml_num_candidates = get_arg_or_default("ml_num_candidates", int, 10)

    user_id = request.args.get("user-id")
    if not user_id:
        err_return = get_error_return(
            "Request needs to include valid user-id query params"
        )
        return err_return

    ids_list = request.args.get("ids")
    if not ids_list:
        err_return = get_error_return("Request needs to include valid ids query params")
        return err_return

    query_shifts = [_id.strip() for _id in ids_list.split(",")]

    headers = {"Authorization": request.headers["Authorization"]}

    TZBACKEND_URL = os.getenv("TZBACKEND_URL")

    qssec = fetch_shifts_start_end_created(query_shifts, TZBACKEND_URL, headers)

    ml_recommend_list = machine_learning_query(
        ml_recommend, qssec, query_shifts, ml_num_candidates
    )

    qsse = list(map(lambda x: (x[0], x[1]), qssec))

    busy_users_list = fetch_busy_users(qsse, TZBACKEND_URL, headers)

    unavailable_list = fetch_unavailable_users(qsse, TZBACKEND_URL, headers)

    ineligible_users_list = fetch_ineligible_users(
        query_shifts, TZBACKEND_URL, headers, user_id
    )

    no_work_hrs_list = fetch_no_work_hrs(qsse, TZBACKEND_URL, headers)

    excluded_users_list = lists_union(
        busy_users_list,
        unavailable_list,
        ineligible_users_list,
        no_work_hrs_list,
    )

    user_ids = get_user_ids(TZBACKEND_URL, headers)

    expanded_user_ids = [user_ids for i in range(len(excluded_users_list))]

    feasible_list = lists_difference(expanded_user_ids, excluded_users_list)

    list_shuffle(feasible_list)

    ml_feasible_list = lists_difference(ml_recommend_list, excluded_users_list)

    res_list = concoct(ml_feasible_list, feasible_list, number_to_return)

    return object_and_200(res_list)
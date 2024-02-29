
 

"""
GPT-3 + Yelp Genie skill 
Bro I swear, using our own dataset is more work than the whole other part
"""

import sys
import os
import re
from typing import List
import argparse
import logging
import requests
from datetime import datetime
import html
import json
from utils import print_chatbot, input_user, num_tokens_from_string, if_usable_restaurants, handle_opening_hours
import readline  # enables keyboard arrows when typing in the terminal
import time
from postgresql_connection import execute_sql
# from query_reviews import review_server_address
from sql_free_text_support.execute_free_text_sql import suql_execute
from pglast import parse_sql
from pglast.stream import RawStream
from decimal import Decimal
import math
import prompt_continuation, openai
from prompt_continuation import openai_chat_completion_with_backoff
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from prompt_continuation import llm_generate, batch_llm_generate

logger = logging.getLogger(__name__)

class DialogueTurn:
    def __init__(
        self,
        agent_utterance: str = None,
        user_utterance: str = None,
        genie_utterance: str = None,
        temp_target : str = None,
        user_target : str = None,
        sys_type : str = None,
        time_statement : dict = None,
        db_results : list = [],
        cache : dict = {},
        results_for_ned : dict = None
    ):
        self.agent_utterance = agent_utterance
        self.user_utterance = user_utterance
        self.genie_utterance = genie_utterance
        self.temp_target = temp_target
        self.user_target = user_target
        self.sys_type = sys_type
        self.db_results = db_results
        self.results_for_ned = results_for_ned
        time_statement = time_statement
        
    agent_utterance: str
    user_utterance: str
    genie_utterance: str
    user_target: str
    temp_target: str
    sys_type: str
    time_statement: dict
    db_results: list
    results_for_ned: dict

    def to_text(self, they='They', you='You'):
        """
        Format:
        You: 
        They:
        [You check the database for "find chinese restaurants near palo alto"]
        [Database returns "I see Jing Jing Chinese Gourmet. It is a Chinese restaurant rated 3.5 stars."]
        Restaurant reviews: [
        Review 1: ...
        Summary:
        Review 2: ...
        Summary:
        Review 3: ...
        Summary:
        ]
        """
        ret = ''
        
        ret += they + ': ' + self.user_utterance
        if self.genie_utterance is not None:
            # print(self.genie_utterance)
            ret += '\n' + '[Database returns "' + self.genie_utterance + '"]'
        if self.agent_utterance is not None:
            ret += '\n' + you + ': ' + self.agent_utterance
        return ret


def dialogue_history_to_text(history: List[DialogueTurn], they='They', you='You') -> str:
    """
    From the agent's point of view, it is 'You:'. The agent starts the conversation.
    """
    ret = ''
    for i in range(len(history)):
        ret += '\n' + history[i].to_text(they=they, you=you)

    if len(history) > 0:
        # remove the extra starting newline
        if ret[0] == '\n':
            ret = ret[1:]

    return ret

# a custom function to define what to include in the final response prompt
# this function is used for the restuarants domain, with some processing code
# to deal with `rating` (a float issue)
# and `opening_hours` (represented as a dictionary, but is too long)
def clean_up_response(results, column_names):
    final_res = []
    for res in results:
        temp = dict((column_name, result) for column_name, result in zip(column_names, res) if if_usable_restaurants(column_name))
        for i in temp:
            if isinstance(temp[i], Decimal):
                temp[i] = float(temp[i])
            
        if "opening_hours" in temp:
            temp["opening_hours"] = handle_opening_hours(temp["opening_hours"])
            
        
        # here is some simple heuristics to deal with too long DB results,
        # thus cutting it at some point
        if num_tokens_from_string(json.dumps(final_res + [temp], indent=4)) > 3500:
            break
        
        final_res.append(temp)
    return final_res

# this function extracts only the _id and name fields from the database results, if any
def extract_id_name(results, column_names):
    results_for_ned = []
    for result in results:
        temp = dict((column_name, each_result) for column_name, each_result in zip(column_names, result))
        if "_id" in temp and "name" in temp:
            results_for_ned.append({
                "_id": temp["_id"],
                "name": temp["name"]
            })
    return results_for_ned

def parse_execute_sql(dlgHistory, user_query, prompt_file='prompts/parser_sql.prompt'):
    first_sql, first_sql_time = llm_generate(template_file=prompt_file,
                engine='gpt-3.5-turbo-0613',
                stop_tokens=["Agent:"],
                max_tokens=300,
                temperature=0,
                prompt_parameter_values={'dlg': dlgHistory, 'query': user_query},
                postprocess=False)
    print("directly generated SUQL query: {}".format(first_sql))
    second_sql_start_time = time.time()
    
    first_sql = first_sql.replace("\\'", "''")
    if not ("LIMIT" in first_sql):
        first_sql = re.sub(r';$', ' LIMIT 3;', first_sql, flags=re.MULTILINE)


    if not ("LIMIT" in second_sql):
        second_sql = re.sub(r';$', ' LIMIT 3;', second_sql, flags=re.MULTILINE)
    second_sql = process_query(second_sql)
    second_sql = process_query_opening_hours(second_sql)
    print("HERE IS THE SECOND SQL",second_sql,"\n")

    final_res, column_names, cache = suql_execute(second_sql, fts_fields=[("restaurants", "name")])
    results_for_ned = extract_id_name(final_res, column_names)
    final_res = clean_up_response(final_res, column_names)
        
    second_sql_end_time = time.time()
    
    return final_res, first_sql, second_sql, first_sql_time, second_sql_end_time - second_sql_start_time, cache, results_for_ned

def turn_db_results2name(db_results):
    res = []
    for i in db_results:
        if "name" in i:
            res.append(i["name"])
    return res

def compute_next_turn(
    dlgHistory : List[DialogueTurn],
    user_utterance: str):
    
    first_classification_time = 0
    semantic_parser_time = 0
    suql_execution_time = 0
    final_response_time = 0
    cache = {}

    dlgHistory.append(DialogueTurn(user_utterance=user_utterance))
    dlgHistory[-1].sys_type = "suql_v0102"
    
    # determine whether to use database
    continuation, first_classification_time = llm_generate(template_file='prompts/if_db_classification.prompt', prompt_parameter_values={'dlg': dlgHistory}, engine='gpt-3.5-turbo-0613',
                                max_tokens=50, temperature=0.0, stop_tokens=['\n'], postprocess=False)

    if continuation.startswith("Yes"):
        results, first_sql, second_sql, semantic_parser_time, suql_execution_time, cache, results_for_ned = parse_execute_sql(dlgHistory, user_utterance, prompt_file='prompts/parser_sql.prompt')
        dlgHistory[-1].genie_utterance = json.dumps(results, indent=4)
        dlgHistory[-1].user_target = first_sql
        dlgHistory[-1].temp_target = second_sql
        dlgHistory[-1].db_results = turn_db_results2name(results)
        dlgHistory[-1].results_for_ned = results_for_ned

        # cut it out if no response returned
        if not results:
            response, final_response_time = llm_generate(template_file='prompts/yelp_response_no_results.prompt', prompt_parameter_values={'dlg': dlgHistory}, engine='gpt-3.5-turbo-0613',
                                max_tokens=400, temperature=0.0, stop_tokens=[], top_p=0.5, postprocess=False)
            dlgHistory[-1].agent_utterance = response
            dlgHistory[-1].time_statement = {
                "first_classification": first_classification_time,
                "semantic_parser": semantic_parser_time,
                "suql_execution": suql_execution_time,
                "final_response": final_response_time
            }
            return dlgHistory
            
    response, final_response_time = llm_generate(template_file='prompts/yelp_response_SQL.prompt', prompt_parameter_values={'dlg': dlgHistory}, engine='gpt-3.5-turbo-0613',
                        max_tokens=400, temperature=0.0, stop_tokens=[], top_p=0.5, postprocess=False)
    dlgHistory[-1].agent_utterance = response
    
    dlgHistory[-1].time_statement = {
        "first_classification": first_classification_time,
        "semantic_parser": semantic_parser_time,
        "suql_execution": suql_execution_time,
        "final_response": final_response_time
    }
    dlgHistory[-1].cache = cache
    
    return dlgHistory


def get_location_from_azure(query):

    EARTH_RADIUS = 6371000  # meters
    TOLERANCE = 1500  # meters

    subscription_key = os.environ['AZURE_MAP_KEY']
    # API endpoint
    url = "https://atlas.microsoft.com/search/address/json"

    # Parameters for the request
    params = {
        "subscription-key": subscription_key,
        "api-version": "1.0",
        "language": "en-US",
        "query": query
    }
    # Sending the GET request
    response = requests.get(url, params=params)

    # Extracting the JSON response
    response_json = response.json()

    if response_json['results'][0]['type'] == 'Geography':
        bbox = response_json['results'][0]['boundingBox']
        latitude_north, longitude_west = bbox['topLeftPoint']['lat'], bbox['topLeftPoint']['lon']
        latitude_south, longitude_east = bbox['btmRightPoint']['lat'], bbox['btmRightPoint']['lon']
    else:
        # get coords
        coord = response_json['results'][0]['position']
        longitude, latitude = coord['lon'], coord['lat']

        # Get location range
        delta_longitude = TOLERANCE / EARTH_RADIUS * 180 / math.pi
        delta_latitude = TOLERANCE / (EARTH_RADIUS * math.cos(latitude / 180 * math.pi)) * 180 / math.pi

        longitude_west = longitude - delta_longitude
        longitude_east = longitude + delta_longitude
        latitude_south = latitude - delta_latitude
        latitude_north = latitude + delta_latitude

    return longitude_west, longitude_east, latitude_south, latitude_north

def convert_opening_hours_query(opening_hours_query):
    response, _ = prompt_continuation.llm_generate(
        'prompts/opening_hours.prompt',
        {'opening_hours_query': opening_hours_query},
        engine='gpt-3.5-turbo-0613',
        max_tokens=200,
        temperature=0.0,
        stop_tokens=['\n'],
        postprocess=False
    )
    return response
# Hack: using regex to change all location clauses and opening_hours clauses
def process_query(sql_query):
    print("entered1")
    pattern = r"location\s*=\s*'([^']*)'"
    def replacer(match):
        location_string = match.group(1)
        longitude_west, longitude_east, latitude_south, latitude_north = get_location_from_azure(location_string)
        return f"longitude BETWEEN {longitude_west} AND {longitude_east} AND latitude BETWEEN {latitude_south} AND {latitude_north}"

    return re.sub(pattern, replacer, sql_query)
def process_query_opening_hours(sql_query): 
    print("entered2")
    pattern = r"'([^']*)'\s*=\s*ANY\(CAST opening_hours AS ARRAY\)"
    def replacer(match):
        opening_hours_query = match.group(0).split(" = ")[0]
        opening_hours_translated = convert_opening_hours_query(opening_hours_query) 
        return 'search_by_opening_hours(\"opening_hours\", ' + "'"+ opening_hours_translated + "')" 
    return re.sub(pattern, replacer, sql_query)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output_file', type=str, default='log.log',
                        help='Where to write the outputs, pertaining only to CLI testing.')
    parser.add_argument('--quit_commands', type=str, default=['quit', 'q'],
                        help='The conversation will continue until this string is typed in, pertaining only to CLI testing.')
    parser.add_argument('--no_logging', action='store_true',
                        help='Do not output extra information about the intermediate steps.')
    parser.add_argument('--record_result', type=str, default=None, help='Write results in TSV format to file')
    parser.add_argument('--batch_process', type=str, default=None, help='A list of QA inputs to run')

    args = parser.parse_args()

    if args.no_logging:
        logging.basicConfig(level=logging.CRITICAL, format=' %(name)s : %(levelname)-8s : %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format=' %(name)s : %(levelname)-8s : %(message)s')


    if args.batch_process:
        assert(args.record_result)
        
        with open(args.batch_process, "r") as fd:
            inputs = fd.readlines()
        for each_input in inputs:
            id, utterance = each_input.split('\t')
            utterance = utterance.strip()
            
            dlgHistory = []
            genieDS, genie_aux = None, []
            dlgHistory = compute_next_turn(
                dlgHistory,
                utterance,
            )
            with open(args.record_result, 'a+') as fd:
                fd.write("{}\t{}\t{}\t{}\t{}\n".format(id, dlgHistory[-1].user_utterance, dlgHistory[-1].user_target, dlgHistory[-1].agent_utterance, '\t'.join(dlgHistory[-1].db_results)))

    # The dialogue loop
    # the agent starts the dialogue
    dlgHistory = []
    genieDS, genie_aux = None, []

    print_chatbot(dialogue_history_to_text(dlgHistory, they='User', you='Chatbot'))

    try:
        while True:
            user_utterance = input_user()
            if user_utterance in args.quit_commands:
                break
            
            dlgHistory = compute_next_turn(
                dlgHistory,
                user_utterance,
            )
            print_chatbot('Chatbot: ' + dlgHistory[-1].agent_utterance)
            print(dlgHistory[-1].time_statement)

    finally:
        with open(args.output_file, 'a') as output_file:
            output_file.write('=====\n' + datetime.now().strftime("%d/%m/%Y %H:%M:%S") +
                            '\n' + dialogue_history_to_text(dlgHistory, they='User', you='Chatbot') + '\n')

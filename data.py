import os
import json

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def filter_removing(list):
    result = []
    for item in list:
        if type(item) == dict and 'name' in item and item['name'] == '-':
            pass
        else:
            result.append(item)
    return result

def merge_id(old, new):
    used_id = set()
    for new_item in new:
        used_id.add(new_item['id'])
    for old_item in old:
        if old_item['id'] in used_id:
            pass
        else:
            new.append(old_item)
    return new

def merge_id_deep(old, new, keys):
    merged = dict()
    for new_item in new:
        merged[new_item['id']] = new_item
    for old_item in old:
        if old_item['id'] in merged:
            new_item = merged[old_item['id']]
            for key in keys:
                new_item[key] = merge_id(old_item[key], new_item[key])
                new_item[key] = filter_removing(new_item[key])
            merged[old_item['id']] = new_item
        else:
            merged[old_item['id']] = old_item
    result = []
    for key, value in merged.items():
        result.append(value)
    result = filter_removing(result)
    return result

def merge_data_json(old, new):
    # localStorage.persist:cherry-studio
    old_settings = json.loads(old['localStorage']['persist:cherry-studio'])
    new_settings = json.loads(new['localStorage']['persist:cherry-studio'])
    old_assistants = json.loads(old_settings['assistants'])
    new_assistants = json.loads(new_settings['assistants'])
    new_assistants['assistants'] = merge_id_deep(old_assistants['assistants'], new_assistants['assistants'], ['topics'])
    # new_settings['assistants'] = new_assistants
    new_settings['assistants'] = json.dumps(new_assistants)
    # new['localStorage']['persist:cherry-studio'] = new_settings
    new['localStorage']['persist:cherry-studio'] = json.dumps(new_settings)
    
    # indexedDB
    new['indexedDB']['files'] = merge_id(old['indexedDB']['files'], new['indexedDB']['files'])
    new['indexedDB']['topics'] = merge_id_deep(old['indexedDB']['topics'], new['indexedDB']['topics'], ['messages'])
    
    return new

if __name__ == '__main__':
    old_file = os.path.join(DATA_DIR, "data.json")
    new_file = os.path.join(DATA_DIR, "data_new.json")
    old_json = json.load(open(old_file, 'r', encoding='utf-8'))
    new_json = json.load(open(new_file, 'r', encoding='utf-8'))
    result_json = merge_data_json(old_json, new_json)
    result_file = os.path.join(DATA_DIR, "data_result.json")
    json.dump(result_json, open(result_file, 'w', encoding='utf8'), ensure_ascii=False, indent=4)

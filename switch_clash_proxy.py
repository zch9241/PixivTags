import aiohttp
import json

from tqdm.asyncio import tqdm as async_tqdm

from src.config import *

async def get_clash_nodes(session: aiohttp.ClientSession, selector_name:str, filters:list[str]=[]):
    """获取指定选择器下所有可用的节点名称

    Args:
        session (aiohttp.ClientSession): _description_
        selector_name (str): 选择器名称
        filters (list[str], optional): 筛选器，仅获取包含关键词的节点，设空则禁用此功能. Defaults to [].

    Returns:
        list: 可用节点列表
    """
    url = f"{CLASH_API_HOST}/proxies/{selector_name}"
    headers = {}
    if CLASH_API_SECRET:
        headers['Authorization'] = f'Bearer {CLASH_API_SECRET}'
    try:
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()
        # 'all' 字段包含了所有可用节点的列表
        nodes:list = data.get('all', [])
        if filters:
            def is_in_filter(node: str):
                nonlocal filters
                for _filter in filters:
                    if _filter in node:
                        return True
                return False
            return list(filter(is_in_filter, nodes))
        else:
            return nodes
    except Exception as e:
        async_tqdm.write(f"[get_clash_nodes] (ERROR) 获取节点失败: {e}")
        return []

async def switch_clash_proxy(session: aiohttp.ClientSession, selector_name: str, new_node_name: str):
    """异步切换Clash指定选择器的节点

    Args:
        session (aiohttp.ClientSession): _description_
        selector_name (str): 选择器名称
        new_node_name (str): 新节点名称

    Returns:
        Bool: 操作状态
    """
    url = f"{CLASH_API_HOST}/proxies/{selector_name}"
    headers = {'Content-Type': 'application/json'}
    if CLASH_API_SECRET:
        headers['Authorization'] = f'Bearer {CLASH_API_SECRET}'
            
    payload = json.dumps({"name": new_node_name})
    
    try:
        async with session.put(url, data=payload, headers=headers) as response:
            if response.status == 204:
                async_tqdm.write(f"[switch_clash_proxy] (INFO) 切换节点成功: {new_node_name}")
                return True
            else:
                error_text = await response.text()
                async_tqdm.write(f"[switch_clash_proxy] (ERROR) 切换节点失败. Status: {response.status}, Info: {error_text}")
                return False
    except aiohttp.ClientConnectorError as e:
        async_tqdm.write(f"[switch_clash_proxy] (ERROR) 连接错误: 请检查是否运行了clash verge并启用了api ({e})")
        return False
    except Exception as e:
        async_tqdm.write(f"[switch_clash_proxy] (ERROR) 未知错误: {e}")
        return False

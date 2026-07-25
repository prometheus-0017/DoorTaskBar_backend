import window_proxy
from typing import TypedDict,Union,Literal
from window_proxy import WindowProxy
windowsBefore:dict[int,WindowProxy]={}
version=0


class WindowProxyDTO(TypedDict):
    processId:int
    id:int
    originalName:str
    modifiedName:str
    processName:str
    originalIcon:str
    modifiedIcon:str
    pwd:str
    system:str
class WindowChangeInfo(TypedDict):
    type:Literal['add','change','delete']
    data:WindowProxyDTO

from typing import Callable,Awaitable
callbacklist:dict[str,Callable[[list[WindowChangeInfo]],Awaitable[None]]]={}

import asyncio
from logging import getLogger
logger=getLogger(__name__)
import logging
logging.basicConfig(level=logging.INFO,filemode='log.txt')
async def setCallback(context,id,callback):
    # 必须得标记callback的身份,因为无法确认对面是真的走了还是网络暂时断开
    callbacklist[id]=callback
    
def startWindowsDetectLoop():
    async def loop():
        while True:
            try:
                await asyncio.sleep(1);
                await detectChange()
            except Exception as e:
                traceback.print_exc()
    asyncio.ensure_future(loop())

from websockets.exceptions import ConnectionClosedError
async def _notify(infos:list[WindowChangeInfo]):
    for key in callbacklist:
        callback=callbacklist[key]
        try:
            await callback(infos)
        except ConnectionClosedError:
            # callbacklist.remove(callback)
            pass
        except Exception as e:
            import traceback
            traceback.print_exc()
            del callbacklist[key]
async def echo(context):
    return '1'
async def checkLogin(context,id:str):
    return id in callbacklist

class ChromeProxy:
    async def sync(self)->list[WindowProxyDTO]:
        ...
    async def toTop(self,windowsId:str):
        ...
    async def getHost(self)->str:
        ...
chromeClients:dict[str,ChromeProxy]={}
import traceback
async def loginChrome(context,chromeProxy):
    hostId=await chromeProxy.getHost()
    chromeClients[hostId]=chromeProxy
    if(hostId in chromeClients):
        # reconnecting, last client's ws is disconnected
        pass
    else:
        # as first time, maybe
        lst=await chromeProxy.sync()
        lst=[WindowChangeInfo(type='add',data=x) for x in lst]
        asyncio.ensure_future(_notify(lst))

async def sync(context):
    res=[]
    res+= [WindowProxyDTO(
        processId=v.getProcess(),
        id=v.getId(),
        pwd=v.getPwd(),
        system='win',
        originalName=v.getTitle(),
        modifiedName='',
        processName=v.getProcessFileName(),
        originalIcon=v.getIconPath(),
        modifiedIcon=v.getIconPath()
    ) for v in windowsBefore.values()]
    for clientChrome in chromeClients.keys():
        try:
            res+=await chromeClients[clientChrome].sync()
        except Exception as e:
            traceback.print_exc()
            
    return res
async def detectChange():
    global windowsBefore

    windowList:list[WindowProxy]=WindowProxy.getTopWindow().listChildren()
    windowsNow={item.hwnd:item for item in windowList}
    infoUpdates:list[WindowChangeInfo]=[]
    old=[windowsBefore[k] for k in windowsBefore.keys()-windowsNow.keys()]
    new=[windowsNow[k] for k in windowsNow.keys()-windowsBefore.keys()]
    common=[windowsNow[k] for k in windowsNow.keys()&windowsBefore.keys() if(windowsBefore[k].getPrevName()!=windowsNow[k].getTitle())]
    for v in old:
        logger.info(f'delete {v.getId()} {v.getTitle()}')
    for v in new:
        logger.info(f'add {v.getId()} {v.getTitle()}')
        v.saveIcon()
    for v in new:
        v.saveIcon()
    for v in common:
        v.saveName()
    infoUpdates.extend([WindowChangeInfo(
        type='delete',
        data=WindowProxyDTO(
            processId=v.getProcess(),
            id=v.getId(),
            pwd=v.getPwd(),
            system='win',
            originalName=v.getTitle(),
            modifiedName='',
            processName=v.getProcessFileName(),
            originalIcon=v.getIconPath(),
            modifiedIcon=v.getIconPath()
        ) )for v in old])
    infoUpdates.extend([WindowChangeInfo(
        type='add',
        data=WindowProxyDTO(
            processId=v.getProcess(),
            id=v.getId(),
            pwd=v.getPwd(),
            system='win',
            originalName=v.getTitle(),
            modifiedName='',
            processName=v.getProcessFileName(),
            originalIcon=v.getIconPath(),
            modifiedIcon=v.getIconPath()
        ) )for v in new])
    infoUpdates.extend([WindowChangeInfo(
        type='change',
        data=WindowProxyDTO(
            processId=v.getProcess(),
            id=v.getId(),
            pwd=v.getPwd(),
            system='win',
            originalName=v.getTitle(),#with lock when sync
            modifiedName='',
            processName=v.getProcessFileName(),
            originalIcon=v.getIconPath(),
            modifiedIcon=v.getIconPath()
        )
    ) for v in common])

    windowsBefore=windowsNow
    # await notify(infoUpdates)
    if(infoUpdates.__len__()!=0):
        asyncio.ensure_future(_notify(infoUpdates))
async def notify(contiext,infos:list[WindowChangeInfo]):
    if(type(infos)!=list):
        print('unknown notifyData',infos)
        return 
    await _notify(infos)
import json
def saveStatus(sess,status):
    with open('status.json','w',encoding='utf-8') as f:
        f.write(json.dumps(status,ensure_ascii=False))
    return True
def loadStatus(sess):
    try:
        with open('status.json','r',encoding='utf-8') as f:
            return json.loads(f.read())
    except :
        return None
async def toTop(sess,windowId,system=None):
    if(system==None or system=='win'):
        window_proxy.setTop(windowId)
        return
    for client in chromeClients.values():
        try:
            if(await client.getHost()==system):
                await client.toTop(windowId)
        except Exception as e:
            print('chrome totop failed,current id:',system)
            print('exist client:')
            for key in chromeClients.keys():
                try:
                    await chromeClients[key].getHost()
                    connecting=True
                except:
                    connecting=False
                print(f'[{key}]:{connecting}')
            traceback.print_exc()
    pass
from ui import getWindow
def exit(sess):
    getWindow().exitSignal.emit()
def expand(sess):
    getWindow().expandSignal.emit()
def collapse(sess):
    getWindow().collapseSignal.emit()

def pin(sess,boolValue):
    from conf import conf
    conf['pin']=boolValue
    return  boolValue
import requests, time
import dashscope
import torch
import json
import re
import os
from runner.logger import Logger
from llm.prompts import prompts_fewshot_parse

# 从文件中直接加载BASE_URL和API_KEY
# 判断文件是否存在
if os.path.exists("llm_config.json"):
    with open("llm_config.json", "r") as f:
        llm_config = json.load(f)
        BASE_URL = llm_config.get("base_url", "")
        API_KEY = llm_config.get("api_key", "")

def model_chose(step,model="gpt-4 32K",base_url=BASE_URL,api_key=API_KEY):
    # 检查base_url和api_key是否为空
    if not base_url or not api_key:
        raise ValueError("Base URL and API Key must be provided in llm_config.json")
    # 国外模型
    if model.lower().startswith("gpt") or model.startswith("claude") or model.startswith("gemini"):
        return gpt_req(step,model)
    # 国内模型
    if model.lower().startswith("glm") or model.startswith("qwen") or model.startswith("deepseek"):
        return gpt_req(step,model)


class req:

    def __init__(self,step,model) -> None:
        self.Cost = 0
        self.model=model
        self.step=step

    def log_record(self,prompt_text,output):
        logger=Logger()
        logger.log_conversation(prompt_text, "Human", self.step)
        logger.log_conversation(output, "AI", self.step)

    def fewshot_parse(self, question, evidence, sql):
        s = prompts_fewshot_parse().parse_fewshot.format(question=question,sql=sql)
        ext = self.get_ans(s)
        ext=ext.replace('```','').strip()
        ext = ext.split("#SQL:")[0]# 防止没按格式生成 至少保留SQL
        ans = self.convert_table(ext, sql)
        return ans
    def convert_table(self, s, sql):
        l = re.findall(' ([^ ]*) +AS +([^ ]*)', sql)
        x, v = s.split("#values:")
        t, s = x.split("#SELECT:")
        for li in l:
            s = s.replace(f"{li[1]}.", f"{li[0]}.")
        return t + "#SELECT:" + s + "#values:" + v

def request(url,model,messages,temperature,top_p,n,key,**k):
    res = requests.post(
                url=
                url,
                json={
                    "model":
                    model,
                    "messages": [{
                        "role": "system",
                        "content":
                        "You are an SQL expert, skilled in handling various SQL-related issues."
                    }, {
                        "role": "user",
                        "content": messages
                    }],
                    "max_tokens":
                    800,
                    "temperature":
                    temperature,
                    "top_p":top_p,
                    "n":n,
                    **k
                },
                headers={
                    "Authorization":
                    key
                }).json()

    return res

class gpt_req(req):

    def __init__(self,step,model="glm-5",base_url=BASE_URL,api_key=API_KEY) -> None:
        super().__init__(step,model)
        self.base_url=base_url
        self.api_key=api_key

    def get_ans(self, messages, temperature=0.0, top_p=None,n=1,single=True,**k):
        count = 0
        while count < 50:
            # print(messages) #保存prompt和答案
            try:
                res = request(
                url=self.base_url,
                model=self.model,
                messages= messages,
                temperature=temperature,
                top_p=top_p,
                n=n,
                key=self.api_key,
                **k)
                if n==1 and single:
                    response_clean = res["choices"][0]["message"]["content"]
                else:
                    response_clean = res["choices"]
                # print(self.step)
                if self.step!="prepare_train_queries":
                    self.log_record(messages, response_clean)  # 记录对话内容
                break

            except Exception as e:
                count += 1
                time.sleep(2)
                # print(messages)
                print(e, count, self.Cost,res)

        self.Cost += res["usage"]['prompt_tokens'] / 1000 * 0.042 + res[
            "usage"]["completion_tokens"] / 1000 * 0.126
        return response_clean
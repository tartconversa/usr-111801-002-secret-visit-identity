# 景区资料协作台账：暗访记录的身份与争议归属

服务登记资料来源、字段、原件、使用许可、数据产品与交付凭据，并维护景区主体身份沿革、材料归属、质疑裁定与评级摘要。示例主体和记录均为虚构，不连接真实文旅部门。

需要 Python 3.10 或更新版本，不依赖第三方包。

运行项目测试：python -m unittest discover -s tests -v。
检查源码：python -m compileall -q exchange。
运行本地演练：python -m exchange --database demo.db。

exchange/catalog.py 登记来源字段和原件，grants.py 与 policy.py 管理使用边界，products.py 编排资料，delivery.py 出具回执，audit.py 记录操作。

identity.py 登记景区主体与名称沿革，处理更名、合并、拆分并留存身份事件；attribution.py 把原件按主体编号归属到景区，保留申报名称与依据，支持核对与更正；responses.py 记录答复与观察的对应，双方各自保持来源与版本；disputes.py 管理质疑的提出与裁定；conclusions.py 生成评级摘要，只把无争议或质疑已驳回的观察列为已确认事实，逐条记录采用或排除的理由并钉住所依据的归属版本。身份合并或拆分后，原有归属、答复关系与结论逐项留痕，可经 conclusions.trace 追溯谁对哪条观察作过答复、历次结论为何采用或排除它。

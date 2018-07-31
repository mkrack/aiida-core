from aiida.orm.data.int import Int
from aiida.work.launch import run
from aiida.work.workchain import WorkChain

class AddAndMultiplyWorkChain(WorkChain):
    ...

result = run(AddAndMultiplyWorkChain, a=Int(1), b=Int(2), c=Int(3))
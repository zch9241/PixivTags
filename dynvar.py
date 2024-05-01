for i in range(6):
    exec('var{} = {}'.format(i, i))
print(var0, var1, var2, var3 ,var4 ,var5)
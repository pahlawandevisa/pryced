#!/usr/bin/env python2
# -*- coding: utf-8

# prices watcher (ozon.ru, read.ru)
# скрипт для наблюдения за указанными книгами на ozon.ru, read.ru, my-shop.ru,
# ukazka.ru, bolero.ru, labirint.ru, bgshop.ru, setbook.ru

try:
   from parsing import *
   from BeautifulSoup import BeautifulSoup
except:
   print u'Для работы нужна библиотека BeautifulSoup\n(Можно найти на сайте: http://code.google.com/p/pryced/downloads/list)\n'
   exit()
import datetime # для datetime.datetime.now()
import sqlite3
import sys
import urllib2
#import codecs
import Queue
import threading
import time # для подсчета времени сканирования ссылок

try:
   from ctypes import windll
   handle = windll.kernel32.GetStdHandle(-11)
except:
   pass
# признак запуска на windows-python
win32 = sys.platform.find(u'win')
# cygwin-python за window не считать!
if sys.platform.find(u'cygwin') > -1:
   win32 = -1
# номера цветов текста
FG_BLACK     = 0x0000
FG_BLUE      = 0x0001
FG_GREEN     = 0x0002
FG_CYAN      = 0x0003
FG_RED       = 0x0004
FG_MAGENTA   = 0x0005
FG_YELLOW    = 0x0006
FG_GREY      = 0x0007
FG_INTENSITY = 0x0008 # жирность текста
# номера цветов фона
BG_BLACK     = 0x0000
BG_BLUE      = 0x0010
BG_GREEN     = 0x0020
BG_CYAN      = 0x0030
BG_RED       = 0x0040
BG_MAGENTA   = 0x0050
BG_YELLOW    = 0x0060
BG_GREY      = 0x0070
BG_INTENSITY = 0x0080 # жирность фона
def console_color(color):
   windll.kernel32.SetConsoleTextAttribute(handle, color)

def connect_to_base():
    """ подключение к базе, создание таблиц

    """
    connect = sqlite3.connect('myozon.db')
    cursor = connect.cursor()
    try:
        cursor.execute('create table IF NOT EXISTS books \
        (id integer primary key AUTOINCREMENT, \
        isbn text, title text, author text)')
        connect.commit()
    except sqlite3.Error, e:
        print u'Ошибка при создании таблицы:', e.args[0]
    try:
        cursor.execute('create table IF NOT EXISTS links \
        (id integer primary key AUTOINCREMENT, \
        book int,\
        urlname text, title text, author text, \
        serial text, desc1 text, desc2 text, \
        timestamp DEFAULT current_timestamp)')
        connect.commit()
    except sqlite3.Error, e:
        print u'Ошибка при создании таблицы:', e.args[0]
    try:
        cursor.execute('create table IF NOT EXISTS prices \
        (id integer primary key AUTOINCREMENT, \
        link int, price int, \
        timestamp DEFAULT current_timestamp)')
        connect.commit()
    except sqlite3.Error, e:
        print u'Ошибка при создании таблицы:', e.args[0]

    # добавление колонки для версии без состояния
    try:
        connect.execute('ALTER TABLE links ADD COLUMN state int;')
        connect.execute("VACUUM")
    except:
        pass
    cursor.close()
    return connect

def insert_new_book(connect, isbn, title, author):
   """ загрузка новой книги в свою базу

   """
   book_id = 0
   try:
      cursor = connect.cursor()
      # поиск по вхождению, т.к. некоторые сайты дают одной книге несколько ISBN
      # (например, ozon.ru)
      if len(isbn) > 0: param = ['%'+isbn+'%']
      else: param = ['']
      cursor.execute('select id from books where isbn like ?', param)
      books_data = cursor.fetchall()
      cursor.close()
      if len(books_data) > 0:
         for book_data in books_data:
            book_id = book_data[0]
      else:
         try:
            cursor = connect.cursor()
            cursor.execute( 'insert into books (isbn, title, author) \
               values (?, ?, ?)', (isbn, title, author) )
            book_id = cursor.lastrowid
            cursor.close()
            connect.commit()
         except sqlite3.Error, e:
            print u'Ошибка при выполнении запроса:', e.args[0]
   except sqlite3.Error, e:
      print u'Ошибка при выполнении запроса:', e.args[0]
   return book_id

def load_link(connect, now_day, url_name, create_flag):
   """ загрузка новой ссылки на книгу в свою базу
   """
   try:
      if create_flag > 0:
         cursor = connect.cursor()
            # проверить нет ли уже такой ссылки в базе
         cursor.execute('select author, title from links where urlname like ?',\
                        ['%'+url_name+'%'])
         data = cursor.fetchall()
         cursor.close()
         if len(data) > 0:
            print u'Ссылка на "' + data[0][0] + u'. ' + data[0][1] + \
                  u'" уже существует в базе!'
            return 0;
      if url_name.find(u'ozon.ru') > -1:
         (title, author, serial, isbn, desc2, price) = ozonru_parse_book(url_name, create_flag)
      else:
         f = urllib2.urlopen(url_name) 
         datas = f.read()
         f.close()
         soup = BeautifulSoup(datas)
         if url_name.find(u'read.ru') > -1: 
            (title, author, serial, isbn, desc2, price) = readru_parse_book(soup, create_flag)
         elif url_name.find(u'my-shop.ru') > -1: 
            (title, author, serial, isbn, desc2, price) = myshop_parse_book(soup, create_flag)
         elif url_name.find(u'ukazka.ru') > -1: 
            (title, author, serial, isbn, desc2, price) = ukazka_parse_book(soup, create_flag)
         elif url_name.find(u'bolero.ru') > -1: 
            (title, author, serial, isbn, desc2, price) = bolero_parse_book(soup, create_flag)
         elif url_name.find(u'labirint.ru') > -1:
            (title, author, serial, isbn, desc2, price) = labiru_parse_book(soup, create_flag)
         elif url_name.find(u'bgshop.ru') > -1:
            (title, author, serial, isbn, desc2, price) = bgshop_parse_book(soup, create_flag)
         elif url_name.find(u'setbook.ru') > -1:
            (title, author, serial, isbn, desc2, price) = setbook_parse_book(soup, create_flag)
         else:
            return 0
      if create_flag > 0:
         # в desc2 возвращается в случае фатальной ошибки загрузки
         if desc2 != None:
            try:
               book_id = insert_new_book(connect, isbn, title, author)
               cursor = connect.cursor()
               cursor.execute( 'insert into links \
                  (book, urlname, title, author, serial) \
                  values (?, ?, ?, ?, ?)', \
                  (book_id, url_name, title, author, serial) )
               cursor.close()
               connect.commit()
               print u'Ссылка на "' + author + u'. ' + \
                  title + u'" добавлена в базу.'
            except sqlite3.Error, e:
               print u'Ошибка при выполнении запроса:', e.args[0]
         else:
               print u'Ошибка при извлечения данных о книге:' 
               print u'title:  ' + title
               print u'author: ' + author
               print u'serial: ' + serial
               print u'isbn:   ' + isbn
               print u'price:  ' + price
               print u'desc2:  ' + desc2
      return int(float(price.replace(',', '.')))
   except Exception, e:
      print e
      return 0

def insert_new_price_into_db(connect, results):
   """ сохранение в свою базу цен для книг в списке results

   """
   cursor = connect.cursor()
      # сохранение текущих цен в базе
   for price in results:
      cursor.execute( 'insert into prices (timestamp, link, price) values (?, ?, ?)', price )
   cursor.close()
   connect.commit()
   print u'Цены обновлены.'

class parseThread (threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
       while True:
          row = queue.get()
          result = (row, load_link(None, None, row[1], 0), self.getName())
#          print self.getName(), row[1]
          queue_out.put(result)
          queue.task_done()

class countThread (threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.sz = 0
    def run(self):
       while True:
          if self.sz < queue_out.qsize():
              self.sz = queue_out.qsize()
               # стереть вывод и переместиться в начало строки
              sys.stdout.write('\r' + 5 * ' ' + '\r')
              print(self.sz),
              sys.stdout.flush() # допечатать вывод
       print u'\n'

def countLinks(connect):
   """ получение количества ссылок на книги
      
   """
   count_links = 0
   cursor = connect.cursor()
   cursor.execute('select count(links.id) \
                   from links \
                   left join books on links.book = books.id')
   rows = cursor.fetchall()
   for row in rows:
       count_links = row[0]
   cursor.close()
   return count_links

def run_load_new_price(connect, now_day):
   """ получение текущих цен для имеющихся книг,
   "   сохранение цен в свою базу при insert_mode == 1

   """
   # создать пучёк потоков для загрузки данных.
   # с их количеством надо экспериментировать, 
   # потому что слишком большое количество серьёзно загружает проц
   for i in range(25):
      t = parseThread()
      t.daemon = True # если True, то программа не завершится, пока не закончится выполнение потока
      t.start()
   # создать поток для вывод информации о статусе загрузки
   t = countThread()
   t.daemon = True
   t.start()
   
   print u'Всего ссылок на книги:', countLinks(connect)

   # запрос ссылок из базы
   cursor = connect.cursor()
   cursor.execute('select links.id, links.urlname, books.author || ", " || books.title \
                        , ifnull(min(prices.price),0)\
                        , ifnull(max(prices.price),0)\
                        , books.author, books.title\
                   from links \
                   left join prices on links.id = prices.link \
                   left join books on links.book = books.id \
                   group by links.id, links.author, links.title \
                   order by books.author, books.title, links.urlname')
   rows = cursor.fetchall()
   results = []
   # заполнить очередь, из которой потоки считываю ссылки для загрузки
   for row in rows:
       queue.put(row)
   cursor.close()
   # приостановить выполнение пока очередь со ссылками не опустеет
   queue.join()
   # счетчики для статистики
   count_all = queue_out.qsize()
   count_min = 0
   count_zero = 0
   count_now_min = 0
   # обработка результатов из очереди, которыю заполнили потоки
   results = []
   while not queue_out.empty():
      (row, price, thread_name) = queue_out.get()
      queue_out.task_done()
      if price > 0:
         results.insert(0, (now_day, row[0], price))
         # вывести на экран только текущие минимальные цены
         if price <= int(row[3]) or int(row[3]) == 0:
            count_min += 1
         if price < int(row[3]):
            print_link_info(row, price)
            count_now_min += 1
      else:
         count_zero += 1
   print u'Статистика:\n\tвсего ссылок:', count_all, \
       u'\n\tв минимуме:', count_min, \
       u'\n\tновых ссылок в минимуме:', count_now_min, \
       u'\n\tв нуле:', count_zero, \
       u'\n\tостальных:', (count_all - count_min - count_zero)
   # сохранить только непустые результаты в базу   
   if len(results) > 0:
      insert_new_price_into_db(connect, results)

def print_link_info(row, price):
   """ печать строки ссылки и полученной цены на экран

   """
   color_sym = u''
   color_price = -1
   if price != 0 :
      if price < int(row[3]): 
         if win32 == -1:
            color_sym = u'\033[1;35m'
         else:
            color_price = FG_RED|FG_INTENSITY|BG_BLACK
      elif price == int(row[3]):
         if win32 == -1:
            color_sym = u'\033[1;36m'
         else:
            color_price = FG_CYAN|FG_INTENSITY|BG_BLACK
      # сокращенное название сайта с подсветкой
   if win32 == -1:
      if row[1].find(u'ozon.ru') > -1:
         site = u'\033[1;46mozon.ru\033[0m: '
      elif row[1].find(U'read.ru') > -1:
         site = u'\033[1;43mread.ru\033[0m: '
      elif row[1].find(U'my-shop.ru') > -1: 
         site = u'\033[1;47mmy-shop\033[0m: '
      elif row[1].find(U'ukazka.ru') > -1: 
         site = u'\033[1;44mukazka \033[0m: '
      elif row[1].find(U'bolero.ru') > -1: 
         site = u'\033[1;45mbolero \033[0m: '
      elif row[1].find(U'labirint.ru') > -1: 
         site = u'\033[1;41mlabiru \033[0m: '
      elif row[1].find(U'bgshop.ru') > -1: 
         site = u'\033[1;41mbgshop \033[0m: '
      elif row[1].find(U'setbook.ru') > -1: 
         site = u'\033[1;41msetbook\033[0m: '
      else:
         site = u'none'
      sys.stdout.write(site)
      close_color = u'\033[0m'
   else:
      if row[1].find(u'ozon.ru') > -1:
         site = u'ozon.ru'
         colornum = FG_GREY|FG_INTENSITY|BG_CYAN|BG_INTENSITY
      elif row[1].find(U'read.ru') > -1:
         site = u'read.ru'
         colornum = FG_GREY|FG_INTENSITY|BG_YELLOW
      elif row[1].find(U'my-shop.ru') > -1: 
         site = u'my-shop'
         colornum = FG_GREY|FG_INTENSITY|BG_GREY
      elif row[1].find(U'ukazka.ru') > -1: 
         site = u'ukazka '
         colornum = FG_GREY|FG_INTENSITY|BG_BLUE|BG_INTENSITY
      elif row[1].find(U'bolero.ru') > -1: 
         site = u'bolero '
         colornum = FG_GREY|FG_INTENSITY|BG_MAGENTA|BG_INTENSITY
      elif row[1].find(U'labirint.ru') > -1: 
         site = u'labiru '
         colornum = FG_GREY|FG_INTENSITY|BG_RED|BG_INTENSITY
      elif row[1].find(U'bgshop.ru') > -1: 
         site = u'bgshop '
         colornum = FG_GREY|FG_INTENSITY|BG_RED|BG_INTENSITY
      elif row[1].find(U'setbook.ru') > -1: 
         site = u'setbook'
         colornum = FG_GREY|FG_INTENSITY|BG_RED|BG_INTENSITY
      else:
         site = u'none'
      console_color(colornum)
      sys.stdout.write(site+u': ')
      console_color(FG_GREY|BG_BLACK)
      color_sym = close_color = u''
   if win32 == -1:
      print(row[2] + u';' + color_sym + \
            u' сейчас: ' + unicode(str(price)) + close_color + \
            u', минимум: ' + unicode(str(row[3])) + \
            u', максимум: ' + unicode(str(row[4])) + u'; ' + row[1])
   else:
      sys.stdout.write(row[2] + u';' + color_sym)
      if color_price > 0:
         console_color(color_price)
      sys.stdout.write(u' сейчас: ' + unicode(str(price)) + close_color )
      console_color(FG_GREY|BG_BLACK)
      print(u', минимум: ' + unicode(str(row[3])) + \
            u', максимум: ' + unicode(str(row[4])) + u'; ' + row[1])
    
def add_new_book(connect, now_day, url_name):
   """ добавление ссылки на книгу в базу

   """
   price = load_link(connect, now_day, url_name, 1)
      # загрузка прошла без осложнений
   if price > 0:
      results = []
      cursor = connect.cursor()
      cursor.execute('select id from links where urlname like ?', ['%'+url_name+'%'] )
      data = cursor.fetchall()
      cursor.close()
      results.insert(0, (now_day, data[0][0], price) )
      insert_new_price_into_db(connect, results)
      print sys.argv[2] + u': цена сейчас:', str(price)

def usage_message():
   """ сообщение о правильном использовании

   """
   msg = u'использование: ' + \
         unicode(sys.argv[0]) + u' {-a|t <ссылка на книгу> | -g}' + \
         u'\n\t-a <ссылка на книгу> - добавить ссылку на книгу в базу' +\
         u'\n\t-t <ссылка на книгу> - проверить ссылку'+\
         u'\n\t-g - получить текущие цены и сохранить их в базу'
   print msg

queue = Queue.Queue()
queue_out = Queue.Queue()

if __name__ == "__main__":
   try:
      #для отладки вывода с исользованием трубы |
      #(win-консоль не понимает utf8)
      #sys.stdout = codecs.getwriter('utf8')(sys.stdout)

          # значение даты для вставки в базу
      now_day = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
      connect = connect_to_base()
      if len(sys.argv) > 2:
         if sys.argv[1] == '-a': # добавление ссылки на книгу в базу
            add_new_book(connect, now_day, sys.argv[2])
         elif sys.argv[1] == '-t': # проба ссылки
            test_url(sys.argv[2])
      elif len(sys.argv) > 1 and (sys.argv[1] == '-g'): # добавление текущих цен в базу
         start = time.time()
         try:
            run_load_new_price(connect, now_day)
         except sqlite3.Error, e:
            print u'Ошибка при выполнении:', e.args[0]
         print u'\nВремя работы: %s\n' % (time.time() - start)
      else:
         usage_message()
      connect.close()
   except Exception, e:
      usage_message()
      print e

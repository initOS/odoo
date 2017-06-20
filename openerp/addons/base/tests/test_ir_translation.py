# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2017 initOS GmbH (<http://www.initos.com>).
#    Author: Andreas Zöllner <andreas.zoellner at initos.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import openerp.tests.common

import logging


_logger = logging.getLogger(__name__)


class test_ir_translation(openerp.tests.common.TransactionCase):

    def _create_record(self, model, **kwargs):
        registry, cr, uid = self.registry, self.cr, self.uid
        model_obj = registry(model)
        return model_obj.create(cr, uid, kwargs)

    def _browse_record(self, model, res_id, context=None):
        registry, cr, uid = self.registry, self.cr, self.uid
        model_obj = registry(model)
        return model_obj.browse(cr, uid, res_id, context=context)

    def _create_translation(self, model, field, res_id, lang, src, value):
        data = {
            'lang': lang,
            'type': 'model',
            'state': 'translated',
            'module': 'base',
            'name': '%s,%s' % (model, field),
            'res_id': res_id,
            'src': src,
            'value': value,
        }
        return self._create_record('ir.translation', **data)

    def test_multiple_translation_records(self):
        """
        Having multiple translation records for the same translatable field.
        """
        model = 'res.partner.category'
        name1 = 'Category 1'
        name2 = 'Category 2'
        cat1_id = self._create_record(model, name=name1)
        cat2_id = self._create_record(model, name=name2)

        DE = 'de_DE'
        name1_de = 'Kategorie Eins'
        name2_de = 'Kategorie Zwei'
        self._create_translation(model, 'name', cat1_id, DE, name1, name1_de)
        self._create_translation(model, 'name', cat1_id, DE, name2, name2_de)
        self._create_translation(model, 'name', cat2_id, DE, name1, name1_de)
        self._create_translation(model, 'name', cat2_id, DE, name2, name2_de)

        context_de = {'lang': 'de_DE'}

        cat = self._browse_record(model, cat1_id)
        self.assertEqual(cat.name, name1)

        cat = self._browse_record(model, cat1_id, context=context_de)
        self.assertEqual(cat.name, name1_de)

        cat = self._browse_record(model, cat2_id)
        self.assertEqual(cat.name, name2)

        cat = self._browse_record(model, cat2_id, context=context_de)
        self.assertEqual(cat.name, name2_de)

    def test_call_translation_method_directly(self):
        """
        Directly running the method to determine translations.
        """
        model = 'res.partner.category'
        name1 = u'Category 1'
        name2 = u'Category 2'
        cat1_id = self._create_record(model, name=name1)

        DE = 'de_DE'
        name1_de = u'Kategorie Eins'
        name2_de = u'Kategorie Zwei'
        self._create_translation(model, 'name', cat1_id, DE, name1, name1_de)
        self._create_translation(model, 'name', cat1_id, DE, name2, name2_de)

        registry, cr, uid = self.registry, self.cr, self.uid
        translation_obj = registry('ir.translation')
        tr_name = '%s,name' % model

        key = cat1_id
        ids = translation_obj._get_ids(cr, uid, tr_name, 'model', DE, [key])
        self.assertEqual(ids, {key: name1_de})

        key = (cat1_id, name1)
        ids = translation_obj._get_ids(cr, uid, tr_name, 'model', DE, [key])
        self.assertEqual(ids, {key: name1_de})

        key = (cat1_id, name2)
        ids = translation_obj._get_ids(cr, uid, tr_name, 'model', DE, [key])
        self.assertEqual(ids, {key: name2_de})

        key = (cat1_id, 'foo')
        # _get_ids will use the fallback case
        ids = translation_obj._get_ids(cr, uid, tr_name, 'model', DE, [key])
        # ... which will ("randomly") result in either `name1_de` or `name1_de`
        self.assertIn(ids, [{key: name1_de}, {key: name2_de}])
